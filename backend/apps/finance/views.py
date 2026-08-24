import logging

from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminRole
from apps.businesses.models import Business
from .assistant import AssistantError, ask_assistant
from .insights import build_insights
from .models import Transaction
from .serializers import TransactionSerializer

logger = logging.getLogger(__name__)


class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Transaction.objects.all()
        business = Business.objects.filter(owner=self.request.user).first()
        if not business:
            return Transaction.objects.none()
        return Transaction.objects.filter(business=business)

    def perform_create(self, serializer):
        business = Business.objects.filter(owner=self.request.user).first()
        serializer.save(business=business)


@api_view(["GET"])
@permission_classes([IsAdminRole])
def business_insights(request):
    """Insights de negócio gerados por IA (com fallback local) para o dashboard."""
    business = Business.objects.filter(owner=request.user).first()
    if not business:
        return Response({"provider": "local-demo", "insights": []})
    provider, insights = build_insights(business)
    return Response({"provider": provider, "insights": insights})


@api_view(["POST"])
@permission_classes([IsAdminRole])
def finance_assistant(request):
    """Chat do assistente financeiro, restrito ao negócio de quem pergunta."""
    business = Business.objects.filter(owner=request.user).first()
    if not business:
        return Response(
            {"detail": "Nenhum negócio encontrado para este usuário."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    messages = request.data.get("messages")
    if not isinstance(messages, list):
        return Response(
            {"detail": "Envie o histórico da conversa em 'messages'."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        provider, answer = ask_assistant(business, messages)
    except AssistantError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
    except Exception:  # noqa: BLE001 - rede de seguranca da integracao
        logger.exception("Erro inesperado no assistente financeiro (business=%s)", business.id)
        return Response(
            {"detail": "O assistente não conseguiu responder agora. Tente de novo."},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response({"provider": provider, "message": answer})
