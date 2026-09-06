import logging

from django.conf import settings
from django.db import transaction as db_transaction
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, parser_classes, permission_classes, throttle_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminRole
from apps.accounts.throttles import AIRateThrottle
from apps.businesses.models import Business
from .assistant import AssistantError, ask_assistant
from .models import AssistantConversation, AssistantMessage
from .insights import build_insights
from .models import StatementImport, Transaction
from .serializers import StatementConfirmSerializer, TransactionSerializer
from .statements import EXTENSOES_ACEITAS, StatementError, hash_arquivo, parse_statement

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


# ---------------------------------------------------------------------------
# Importacao de extrato bancario
# ---------------------------------------------------------------------------
# Sao dois passos de proposito. O primeiro so le e devolve; o segundo grava o
# que o usuario confirmou. Extrato tem transferencia entre contas proprias, que
# nao e receita nem despesa — importar direto sujaria os totais.


@api_view(["POST"])
@permission_classes([IsAdminRole])
@parser_classes([MultiPartParser])
def statement_preview(request):
    """Le o extrato enviado e devolve os lancamentos, sem gravar nada."""
    business = _business_or_none(request)
    if not business:
        return Response(
            {"detail": "Nenhum negocio encontrado para este usuario."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    enviado = request.FILES.get("file")
    if not enviado:
        limite = settings.STATEMENT_MAX_UPLOAD_BYTES // (1024 * 1024)
        return Response(
            {"detail": f"Envie o arquivo do extrato (ate {limite} MB)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if enviado.size > settings.STATEMENT_MAX_UPLOAD_BYTES:
        limite = settings.STATEMENT_MAX_UPLOAD_BYTES // (1024 * 1024)
        return Response(
            {"detail": f"Arquivo grande demais. O limite e {limite} MB."},
            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    conteudo = enviado.read()
    try:
        formato, lancamentos = parse_statement(enviado.name, conteudo)
    except StatementError as erro:
        return Response({"detail": str(erro)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        # Arquivo corrompido nao deve virar 500: o usuario precisa saber que o
        # problema esta no arquivo, nao no servidor.
        logger.exception("Falha inesperada ao ler extrato %s", enviado.name)
        return Response(
            {"detail": "Nao foi possivel ler este arquivo. Confirme que e o extrato exportado pelo banco."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    arquivo_hash = hash_arquivo(conteudo)
    ja_existentes = set(
        Transaction.objects.filter(
            business=business,
            external_id__in=[item.external_id for item in lancamentos],
        )
        .exclude(external_id="")
        .values_list("external_id", flat=True)
    )

    linhas = []
    for item in lancamentos:
        linha = item.as_dict()
        linha["duplicate"] = item.external_id in ja_existentes
        linhas.append(linha)

    return Response({
        "filename": enviado.name[:200],
        "file_format": formato,
        "file_hash": arquivo_hash,
        "total": len(linhas),
        "duplicates": sum(1 for linha in linhas if linha["duplicate"]),
        "already_imported": StatementImport.objects.filter(
            business=business, file_hash=arquivo_hash
        ).exists(),
        "transactions": linhas,
    })


@api_view(["POST"])
@permission_classes([IsAdminRole])
def statement_confirm(request):
    """Grava os lancamentos que o usuario manteve na tela de conferencia."""
    business = _business_or_none(request)
    if not business:
        return Response(
            {"detail": "Nenhum negocio encontrado para este usuario."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = StatementConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    dados = serializer.validated_data

    linhas = dados["transactions"]
    identificadores = [linha["external_id"] for linha in linhas if linha["external_id"]]
    ja_existentes = set(
        Transaction.objects.filter(business=business, external_id__in=identificadores)
        .values_list("external_id", flat=True)
    )

    criadas = []
    vistos = set()
    with db_transaction.atomic():
        importacao = StatementImport.objects.create(
            business=business,
            filename=dados["filename"],
            file_format=dados["file_format"],
            file_hash=dados["file_hash"],
        )
        for linha in linhas:
            identificador = linha["external_id"]
            # Pula o que ja existe no banco e o que veio repetido no mesmo envio.
            if identificador and (identificador in ja_existentes or identificador in vistos):
                continue
            if identificador:
                vistos.add(identificador)
            criadas.append(
                Transaction.objects.create(
                    business=business,
                    description=linha["description"],
                    type=linha["type"],
                    amount=linha["amount"],
                    occurred_at=linha["occurred_at"],
                    source=Transaction.Source.IMPORT,
                    external_id=identificador,
                    statement_import=importacao,
                )
            )
        importacao.imported_count = len(criadas)
        importacao.skipped_count = len(linhas) - len(criadas)
        importacao.save(update_fields=["imported_count", "skipped_count"])

    logger.info(
        "Extrato %s importado: %s lancamentos, %s ignorados.",
        dados["filename"], importacao.imported_count, importacao.skipped_count,
    )

    return Response(
        {
            "imported": importacao.imported_count,
            "skipped": importacao.skipped_count,
            "transactions": TransactionSerializer(criadas, many=True).data,
        },
        status=status.HTTP_201_CREATED,
    )
