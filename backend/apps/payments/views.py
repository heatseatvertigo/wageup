import logging

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminRole
from apps.businesses.models import Business
from apps.finance.models import Transaction
from .models import Payment, PaymentEvent
from .serializers import PaymentSerializer, PixChargeCreateSerializer
from .services import AbacatePayClient, AbacatePayError

logger = logging.getLogger(__name__)


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

    @action(detail=True, methods=["post"])
    def check(self, request, pk=None):
        """Consulta o status da cobranca na Abacate Pay e sincroniza o nosso.

        E o que sustenta a tela que acompanha o pagamento: o webhook pode
        nao chegar (nao existe em desenvolvimento, e em producao depende de
        configuracao), entao perguntar ao provedor e o caminho confiavel.
        """
        payment = self.get_object()
        if not payment.provider_payment_id:
            return Response(PaymentSerializer(payment).data)

        try:
            data = AbacatePayClient().check_pix_charge(payment.provider_payment_id)
        except AbacatePayError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:  # noqa: BLE001 - rede de seguranca da integracao
            logger.exception("Erro inesperado ao checar cobranca PIX (payment=%s)", payment.id)
            return Response(
                {"detail": "Nao foi possivel consultar a cobranca agora."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        sync_payment_status(payment, data)
        return Response(PaymentSerializer(payment).data)

    def create(self, request, *args, **kwargs):
        serializer = PixChargeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        business = Business.objects.filter(owner=request.user).first()
        # Os dados do cliente sao enviados ao provedor, mas tambem ficam
        # guardados aqui: sem isso a tela de detalhes nao tem como mostrar
        # para quem a cobranca foi feita.
        customer = {
            key: (data.get(f"customer_{key}") or "").strip()
            for key in ("name", "email", "tax_id", "cellphone")
        }
        payment = Payment.objects.create(
            business=business,
            amount=data["amount"],
            status=Payment.Status.PENDING,
            metadata={
                "description": data.get("description", ""),
                "customer": {k: v for k, v in customer.items() if v},
            },
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
        except Exception as exc:  # noqa: BLE001 - rede de seguranca da integracao
            # Falha inesperada ao falar com o provedor: registra o traceback
            # completo (visivel nos logs do servidor) e devolve uma mensagem
            # utilizavel, em vez de um 500 sem explicacao para o usuario.
            logger.exception("Erro inesperado ao gerar cobranca PIX (payment=%s)", payment.id)
            payment.status = Payment.Status.FAILED
            payment.metadata = {**payment.metadata, "error": f"{type(exc).__name__}: {exc}"}
            payment.save(update_fields=["status", "metadata", "updated_at"])
            return Response(
                {"detail": "Nao foi possivel gerar a cobranca agora. Tente novamente em instantes."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

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
        record_finance_income(payment)
    elif event_type in {"checkout.refunded", "transparent.refunded"}:
        payment.status = Payment.Status.REFUNDED
        record_finance_refund(payment)
    elif event_type in {"checkout.disputed", "transparent.disputed", "transparent.lost"}:
        payment.status = Payment.Status.FAILED
    else:
        return

    payment.metadata = {**payment.metadata, "last_webhook": data}
    payment.save(update_fields=["status", "metadata", "updated_at"])


# Status da Abacate Pay -> status do nosso Payment.
PROVIDER_STATUS = {
    "PENDING": Payment.Status.PENDING,
    "PAID": Payment.Status.PAID,
    "EXPIRED": Payment.Status.EXPIRED,
    "CANCELLED": Payment.Status.CANCELED,
    "CANCELED": Payment.Status.CANCELED,
    "REFUNDED": Payment.Status.REFUNDED,
}

# Uma cobranca paga nao volta a ser pendente/expirada: o dinheiro entrou e ja
# virou lancamento no financeiro. Só estorno altera uma cobranca paga.
STATUS_AFTER_PAID = {Payment.Status.REFUNDED}


def sync_payment_status(payment, data):
    """Aplica no nosso Payment o status informado pelo provedor."""
    mapped = PROVIDER_STATUS.get(str(data.get("status") or "").upper())
    if not mapped:
        return

    if payment.status == Payment.Status.PAID and mapped not in STATUS_AFTER_PAID:
        return

    if mapped == Payment.Status.PAID:
        record_finance_income(payment)
    elif mapped == Payment.Status.REFUNDED:
        record_finance_refund(payment)

    payment.status = mapped
    payment.metadata = {
        **payment.metadata,
        "expiresAt": data.get("expiresAt") or payment.metadata.get("expiresAt"),
        "last_check": data,
    }
    payment.save(update_fields=["status", "metadata", "updated_at"])


def record_finance_income(payment):
    """Concilia o PIX pago com o financeiro criando a entrada correspondente.

    Idempotente: o id da transação criada fica em payment.metadata, então um
    webhook reenviado não duplica o lançamento.
    """
    if not payment.business or payment.metadata.get("finance_transaction_id"):
        return
    description = payment.metadata.get("description") or "Cobrança PIX"
    transaction = Transaction.objects.create(
        business=payment.business,
        description=f"PIX recebido: {description}"[:180],
        type=Transaction.TransactionType.INCOME,
        amount=payment.amount,
        source=Transaction.Source.PIX,
    )
    payment.metadata = {**payment.metadata, "finance_transaction_id": str(transaction.id)}


def record_finance_refund(payment):
    """Registra a saída de estorno quando um PIX já conciliado é reembolsado."""
    if not payment.business:
        return
    if not payment.metadata.get("finance_transaction_id") or payment.metadata.get("refund_transaction_id"):
        return
    description = payment.metadata.get("description") or "Cobrança PIX"
    transaction = Transaction.objects.create(
        business=payment.business,
        description=f"Estorno PIX: {description}"[:180],
        type=Transaction.TransactionType.EXPENSE,
        amount=payment.amount,
        source=Transaction.Source.PIX,
    )
    payment.metadata = {**payment.metadata, "refund_transaction_id": str(transaction.id)}
