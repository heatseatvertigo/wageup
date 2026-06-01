from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Payment, PaymentEvent
from .serializers import PaymentSerializer


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer


@api_view(["POST"])
def abacatepay_webhook(request):
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

    return Response({"detail": "evento recebido", "event_id": str(event.id)}, status=status.HTTP_201_CREATED)

# Create your views here.
