from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminRole
from apps.businesses.models import Business
from .models import Payment, PaymentEvent
from .serializers import PaymentSerializer, PixChargeCreateSerializer
from .services import AbacatePayClient, AbacatePayError


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Payment.objects.all()
        business = Business.objects.filter(owner=self.request.user).first()
        if not business:
            return Payment.objects.none()
        return Payment.objects.filter(business=business)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Consolidação de recebíveis do business: recebido, a receber e recebido no mês."""
        qs = self.get_queryset()
        now = timezone.now()

        paid = qs.filter(status=Payment.Status.PAID)
        pending = qs.filter(status=Payment.Status.PENDING)

        def total(queryset):
            return float(queryset.aggregate(total=Sum("amount"))["total"] or 0)

        return Response({
            "received_total": total(paid),
            "received_this_month": total(
                paid.filter(created_at__year=now.year, created_at__month=now.month)
            ),
            "pending_total": total(pending),
            "paid_count": paid.count(),
            "pending_count": pending.count(),
        })

    def create(self, request, *args, **kwargs):
        serializer = PixChargeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        business = Business.objects.filter(owner=request.user).first()
        payment = Payment.objects.create(
            business=business,
            amount=data["amount"],
            status=Payment.Status.PENDING,
            metadata={"description": data.get("description", "")},
        )

        try:
            charge = AbacatePayClient().create_pix_charge(
                amount_cents=serializer.get_amount_cents(),
                description=data.get("description", ""),
                customer=build_customer(data),
                metadata={"payment_id": str(payment.id)},
            )
        except AbacatePayError as exc:
            payment.status = Payment.Status.FAILED
            payment.metadata = {**payment.metadata, "error": str(exc)}
            payment.save(update_fields=["status", "metadata", "updated_at"])
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        payment.provider_payment_id = charge.get("id", "")
        payment.metadata = {
            **payment.metadata,
            "abacatepay": charge,
            "brCode": charge.get("brCode"),
            "brCodeBase64": charge.get("brCodeBase64"),
            "expiresAt": charge.get("expiresAt"),
        }
        payment.save(update_fields=["provider_payment_id", "metadata", "updated_at"])

        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def abacatepay_webhook(request):
    configured_secret = settings.ABACATE_PAY_WEBHOOK_SECRET
    received_secret = request.query_params.get("webhookSecret", "")
    if configured_secret and received_secret != configured_secret:
        return Response({"detail": "webhook nao autorizado"}, status=status.HTTP_401_UNAUTHORIZED)

    event_id = str(request.data.get("id") or request.data.get("event_id") or "")
    event_type = str(request.data.get("type") or request.data.get("event") or "unknown")

    if not event_id:
        return Response({"detail": "event_id ausente"}, status=status.HTTP_400_BAD_REQUEST)

    event, created = PaymentEvent.objects.get_or_create(
        event_id=event_id,
        defaults={
            "event_type": event_type,
            "raw_payload": request.data,
            "processed_at": timezone.now(),
        },
    )

    if not created:
        return Response({"detail": "evento ja processado"}, status=status.HTTP_200_OK)

    apply_payment_event(event_type, request.data.get("data") or {})

    return Response({"detail": "evento recebido", "event_id": str(event.id)}, status=status.HTTP_201_CREATED)


def build_customer(data):
    # Abacate Pay rejeita o objeto customer com 422 a menos que taxId E
    # cellphone estejam presentes juntos. Omitir o customer inteiro é válido.
    tax_id = (data.get("customer_tax_id") or "").strip()
    cellphone = (data.get("customer_cellphone") or "").strip()
    if not tax_id or not cellphone:
        return None

    customer = {"taxId": tax_id, "cellphone": cellphone}
    if data.get("customer_name"):
        customer["name"] = data["customer_name"].strip()
    if data.get("customer_email"):
        customer["email"] = data["customer_email"].strip()
    return customer


def apply_payment_event(event_type, data):
    transparent = data.get("transparent") or {}
    provider_payment_id = str(transparent.get("id") or data.get("id") or data.get("checkoutId") or "")
    if not provider_payment_id:
        return

    payment = Payment.objects.filter(provider_payment_id=provider_payment_id).first()
    if not payment:
        return

    if event_type in {"checkout.completed", "transparent.completed"}:
        payment.status = Payment.Status.PAID
    elif event_type in {"checkout.refunded", "transparent.refunded"}:
        payment.status = Payment.Status.REFUNDED
    elif event_type in {"checkout.disputed", "transparent.disputed", "transparent.lost"}:
        payment.status = Payment.Status.FAILED
    else:
        return

    payment.metadata = {**payment.metadata, "last_webhook": data}
    payment.save(update_fields=["status", "metadata", "updated_at"])
