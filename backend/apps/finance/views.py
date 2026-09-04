import logging

from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminRole
from apps.accounts.throttles import AIRateThrottle
from apps.businesses.models import Business
from .assistant import AssistantError, ask_assistant
from .models import AssistantConversation, AssistantMessage
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
@throttle_classes([AIRateThrottle])
def business_insights(request):
    """Insights de negócio gerados por IA (com fallback local) para o dashboard."""
    business = Business.objects.filter(owner=request.user).first()
    if not business:
        return Response({"provider": "local-demo", "insights": []})
    provider, insights = build_insights(business)
    return Response({"provider": provider, "insights": insights})


def _serialize_conversation(conversation):
    return {
        "id": str(conversation.id),
        "title": conversation.title,
        "updated_at": conversation.updated_at.isoformat(),
    }


def _serialize_message(message):
    return {
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at.isoformat(),
    }


def _business_or_none(request):
    return Business.objects.filter(owner=request.user).first()


@api_view(["GET", "POST"])
@permission_classes([IsAdminRole])
def assistant_conversations(request):
    """Lista as conversas do negócio ou começa uma nova."""
    business = _business_or_none(request)
    if not business:
        return Response({"detail": "Nenhum negócio encontrado."}, status=status.HTTP_400_BAD_REQUEST)

    if request.method == "POST":
        conversation = AssistantConversation.objects.create(business=business)
        return Response(_serialize_conversation(conversation), status=status.HTTP_201_CREATED)

    conversations = AssistantConversation.objects.filter(business=business)
    return Response([_serialize_conversation(c) for c in conversations])


@api_view(["GET", "DELETE"])
@permission_classes([IsAdminRole])
def assistant_conversation_detail(request, conversation_id):
    """Mensagens de uma conversa, ou remoção dela."""
    business = _business_or_none(request)
    conversation = AssistantConversation.objects.filter(
        id=conversation_id, business=business
    ).first()
    if not conversation:
        return Response({"detail": "Conversa não encontrada."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "DELETE":
        conversation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    return Response({
        **_serialize_conversation(conversation),
        "messages": [_serialize_message(m) for m in conversation.messages.all()],
    })


@api_view(["POST"])
@permission_classes([IsAdminRole])
@throttle_classes([AIRateThrottle])
def finance_assistant(request):
    """Recebe uma pergunta, responde e guarda os dois lados da conversa.

    O histórico vem do banco, não do cliente: além de sobreviver ao recarregar
    a página, impede que o navegador forje o que foi dito antes.
    """
    business = _business_or_none(request)
    if not business:
        return Response(
            {"detail": "Nenhum negócio encontrado para este usuário."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    pergunta = str(request.data.get("message") or "").strip()
    if not pergunta:
        return Response({"detail": "Envie uma pergunta."}, status=status.HTTP_400_BAD_REQUEST)

    conversation_id = request.data.get("conversation_id")
    conversation = None
    if conversation_id:
        conversation = AssistantConversation.objects.filter(
            id=conversation_id, business=business
        ).first()
    if not conversation:
        conversation = AssistantConversation.objects.create(business=business)

    # O título nasce da primeira pergunta — é como o usuário reconhece a
    # conversa na lista depois.
    if not conversation.title:
        conversation.title = pergunta[:80]

    historico = [
        {"role": m.role, "content": m.content}
        for m in conversation.messages.all()
    ]
    historico.append({"role": "user", "content": pergunta})

    try:
        provider, resposta = ask_assistant(business, historico)
    except AssistantError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
    except Exception:  # noqa: BLE001 - rede de seguranca da integracao
        logger.exception("Erro inesperado no assistente financeiro (business=%s)", business.id)
        return Response(
            {"detail": "O assistente não conseguiu responder agora. Tente de novo."},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    # Só grava depois de ter resposta: uma pergunta sem retorno deixaria a
    # conversa torta na próxima vez que fosse carregada.
    AssistantMessage.objects.create(conversation=conversation, role="user", content=pergunta)
    AssistantMessage.objects.create(conversation=conversation, role="assistant", content=resposta)
    conversation.save()

    return Response({
        "provider": provider,
        "message": resposta,
        "conversation": _serialize_conversation(conversation),
    })
