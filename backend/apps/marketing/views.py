import hashlib
import logging

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.throttles import AIRateThrottle
from apps.businesses.models import Business
from .assistant import (
    MAX_MESSAGE_CHARS,
    canal_citado,
    catalogo,
    e_campanha,
    objetivo_citado,
    produto_citado,
    responder,
)
from .images import extrair_prompt, gerar_imagem
from .models import CampaignImage, MarketingCampaign, MarketingConversation, MarketingMessage
from .recommendations import build_recommendations
from .serializers import MarketingCampaignSerializer

logger = logging.getLogger(__name__)


class MarketingCampaignViewSet(viewsets.ModelViewSet):
    serializer_class = MarketingCampaignSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        business = Business.objects.filter(owner=self.request.user).first()
        if not business:
            return MarketingCampaign.objects.none()
        return MarketingCampaign.objects.filter(business=business)

    def perform_create(self, serializer):
        business = Business.objects.filter(owner=self.request.user).first()
        serializer.save(business=business)


def _serialize_conversation(conversation):
    return {
        "id": str(conversation.id),
        "title": conversation.title,
        "updated_at": conversation.updated_at.isoformat(),
    }


def _tem_imagem(campaign):
    if campaign is None:
        return False
    try:
        campaign.image
    except CampaignImage.DoesNotExist:
        return False
    return True


def _serialize_message(message):
    return {
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at.isoformat(),
        "campaign_id": str(message.campaign_id) if message.campaign_id else None,
        "has_image": _tem_imagem(message.campaign),
    }


def _business_or_none(request):
    return Business.objects.filter(owner=request.user).first()


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def marketing_conversations(request):
    """Lista as conversas de marketing do negocio ou comeca uma nova."""
    business = _business_or_none(request)
    if not business:
        return Response({"detail": "Nenhum negócio encontrado."}, status=status.HTTP_400_BAD_REQUEST)

    if request.method == "POST":
        conversation = MarketingConversation.objects.create(business=business)
        return Response(_serialize_conversation(conversation), status=status.HTTP_201_CREATED)

    conversations = MarketingConversation.objects.filter(business=business)
    return Response([_serialize_conversation(c) for c in conversations])


@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def marketing_conversation_detail(request, conversation_id):
    """Mensagens de uma conversa, ou remocao dela.

    Apagar a conversa nao apaga as campanhas: elas continuam na listagem de
    campanhas e seguem contando para as recomendacoes.
    """
    business = _business_or_none(request)
    conversation = MarketingConversation.objects.filter(
        id=conversation_id, business=business
    ).first()
    if business is None or conversation is None:
        return Response({"detail": "Conversa não encontrada."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "DELETE":
        conversation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    mensagens = conversation.messages.select_related("campaign__image")
    return Response({
        **_serialize_conversation(conversation),
        "messages": [_serialize_message(m) for m in mensagens],
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([AIRateThrottle])
def marketing_chat(request):
    """Recebe o pedido livre do usuario, responde e guarda a conversa.

    O historico vem do banco, nao do cliente. Quando a resposta e uma campanha
    (tem "Ideia de imagem"), ela vira uma MarketingCampaign e ganha imagem.
    """
    business = _business_or_none(request)
    if not business:
        return Response(
            {"detail": "Nenhum negócio encontrado para este usuário."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    pedido = str(request.data.get("message") or "").strip()
    if not pedido:
        return Response({"detail": "Escreva o que você quer criar."}, status=status.HTTP_400_BAD_REQUEST)
    pedido = pedido[:MAX_MESSAGE_CHARS]

    conversation = None
    conversation_id = request.data.get("conversation_id")
    if conversation_id:
        try:
            conversation = MarketingConversation.objects.filter(
                id=conversation_id, business=business
            ).first()
        except (ValueError, ValidationError):
            conversation = None
    if conversation is None:
        conversation = MarketingConversation.objects.create(business=business)
    if not conversation.title:
        conversation.title = pedido[:80]

    anteriores = list(conversation.messages.select_related("campaign"))
    historico = [{"role": m.role, "content": m.content} for m in anteriores]
    historico.append({"role": "user", "content": pedido})

    # Produto e canal: o que o pedido cita, senao o da ultima campanha da
    # conversa — "agora faz uma versao para o WhatsApp" continua falando do
    # mesmo produto.
    ultima = next((m.campaign for m in reversed(anteriores) if m.campaign), None)
    produto = produto_citado(pedido, catalogo(business)) or (ultima.product if ultima else None)
    canal = canal_citado(pedido) or (ultima.channel if ultima else None)

    provider, resposta = responder(business, historico, produto=produto, canal=canal)

    campaign = None
    tem_imagem = False
    if e_campanha(resposta):
        campaign = MarketingCampaign.objects.create(
            business=business,
            product=produto,
            prompt=pedido,
            channel=canal or "Instagram",
            goal=objetivo_citado(pedido),
            status=MarketingCampaign.Status.COMPLETED,
            generated_text=resposta,
            provider=provider,
            metadata={"source": provider, "conversation_id": str(conversation.id)},
        )
        tem_imagem = _gerar_imagem_da_campanha(
            campaign, produto.name if produto else "o produto", campaign.channel
        )

    MarketingMessage.objects.create(conversation=conversation, role="user", content=pedido)
    MarketingMessage.objects.create(
        conversation=conversation, role="assistant", content=resposta, campaign=campaign
    )
    conversation.save()

    return Response(
        {
            "provider": provider,
            "message": resposta,
            "conversation": _serialize_conversation(conversation),
            "campaign_id": str(campaign.id) if campaign else None,
            "has_image": tem_imagem,
        },
        status=status.HTTP_201_CREATED,
    )


def _gerar_imagem_da_campanha(campaign, product_name, channel):
    """Gera e guarda a imagem. Devolve se deu certo.

    A imagem e um extra: se nenhum provedor responder, a campanha ja esta
    gravada e o texto ja e util. Por isso nada aqui propaga excecao.
    """
    prompt = extrair_prompt(campaign.generated_text, product_name, channel)
    try:
        resultado = gerar_imagem(prompt)
    except Exception:
        logger.exception("Falha inesperada ao gerar a imagem da campanha.")
        return False

    if resultado is None:
        return False

    provider, conteudo, content_type = resultado
    CampaignImage.objects.update_or_create(
        campaign=campaign,
        defaults={
            "content_type": content_type,
            "data": conteudo,
            "checksum": hashlib.sha256(conteudo).hexdigest(),
            "provider": provider,
            "prompt": prompt,
        },
    )
    return True


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([])
def campaign_image(request, campaign_id):
    """Serve a imagem da campanha.

    Rota autenticada e filtrada por business, como a foto de produto: a
    campanha fala de preco e margem do negocio. Sem throttle de IA — aqui nao
    se gera nada, so se le o que ja esta no banco.
    """
    business = Business.objects.filter(owner=request.user).first()
    imagem = CampaignImage.objects.filter(
        campaign__id=campaign_id, campaign__business=business
    ).first()
    if business is None or imagem is None:
        return Response(
            {"detail": "Esta campanha nao tem imagem."}, status=status.HTTP_404_NOT_FOUND
        )

    etag = f'"{imagem.checksum}"'
    if request.headers.get("If-None-Match") == etag:
        return HttpResponse(status=status.HTTP_304_NOT_MODIFIED)

    resposta = HttpResponse(bytes(imagem.data), content_type=imagem.content_type)
    resposta["ETag"] = etag
    # A imagem da campanha nunca muda depois de gerada.
    resposta["Cache-Control"] = "private, max-age=86400"
    return resposta


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([AIRateThrottle])
def marketing_recommendations(request):
    """Acoes de marketing sugeridas a partir do desempenho do negocio.

    GET porque nao cria nada: a resposta e uma leitura do catalogo. O throttle
    de IA continua valendo, porque o caminho com ANTHROPIC_API_KEY chama o
    modelo e cada chamada custa.
    """
    business = Business.objects.filter(owner=request.user).first()
    if business is None:
        return Response({"provider": "local-demo", "recommendations": []})

    provider, recomendacoes = build_recommendations(business)
    return Response({"provider": provider, "recommendations": recomendacoes})
