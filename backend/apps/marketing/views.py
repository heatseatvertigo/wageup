import logging

import anthropic as anthropic_sdk
from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.throttles import AIRateThrottle
from apps.businesses.models import Business
from .models import MarketingCampaign
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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([AIRateThrottle])
def marketing_chat(request):
    product = request.data.get("product") or {}
    goal = request.data.get("goal") or "promocao"
    channel = request.data.get("channel") or "Instagram"
    prompt = request.data.get("prompt") or "criar uma campanha rapida"

    product_name = product.get("name") or "seu produto"
    price = float(product.get("price") or 0)
    cost = float(product.get("cost") or 0)
    margin = max(price - cost, 0)

    business = Business.objects.filter(owner=request.user).first()
    business_name = business.name if business else ""

    generated_text = None
    provider = "local-demo"
    if settings.ANTHROPIC_API_KEY:
        try:
            generated_text = _call_claude(
                product_name, price, cost, margin, goal, channel, prompt, business_name
            )
            provider = "anthropic"
        except Exception:
            # Chave invalida ou provedor fora do ar nao pode virar erro 500: o
            # usuario fica sem campanha nenhuma por um problema de
            # configuracao. Mesmo caminho que os insights ja seguem.
            logger.exception("Falha ao gerar campanha com a IA. Usando o texto local.")

    if generated_text is None:
        generated_text = _build_demo_campaign(product_name, goal, channel, margin)

    campaign = MarketingCampaign.objects.create(
        business=business,
        prompt=prompt,
        channel=channel,
        goal=goal,
        status=MarketingCampaign.Status.COMPLETED,
        generated_text=generated_text,
        provider=provider,
        metadata={"source": provider},
    )

    return Response(
        {
            "campaign_id": str(campaign.id),
            "message": campaign.generated_text,
            "image_label": f"{product_name}\n{channel}",
        },
        status=status.HTTP_201_CREATED,
    )


def _call_claude(product_name, price, cost, margin, goal, channel, prompt, business_name):
    goal_labels = {
        "promocao": "promoção / oferta especial",
        "lancamento": "lançamento de produto",
        "relacionamento": "relacionamento com clientes",
    }
    goal_label = goal_labels.get(goal, goal)

    system_prompt = (
        "Você é um especialista em marketing digital para pequenos negócios brasileiros. "
        "Crie campanhas objetivas, com linguagem informal e focadas em conversão. "
        "Responda sempre em português brasileiro."
    )

    user_message = (
        f"Crie uma campanha de marketing para o seguinte contexto:\n\n"
        f"Negócio: {business_name or 'microempreendedor'}\n"
        f"Produto: {product_name}\n"
        f"Preço de venda: R$ {price:.2f}\n"
        f"Custo estimado: R$ {cost:.2f}\n"
        f"Margem por unidade: R$ {margin:.2f}\n"
        f"Objetivo da campanha: {goal_label}\n"
        f"Canal: {channel}\n"
        f"Pedido do usuário: {prompt}\n\n"
        f"Estruture a resposta com:\n"
        f"**Chamada principal:** (headline curta e impactante)\n"
        f"**Ideia de imagem:** (descrição visual objetiva)\n"
        f"**Legenda:** (texto para postar no {channel}, com emojis se fizer sentido)\n"
        f"**CTA:** (chamada para ação direta)\n\n"
        f"Seja direto, não use linguagem corporativa e adapte o tom para o {channel}."
    )

    client = anthropic_sdk.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text


def _build_demo_campaign(product_name, goal, channel, margin):
    headlines = {
        "promocao": f"{product_name} com oferta especial por tempo limitado",
        "lancamento": f"Chegou {product_name}: feito para encantar no primeiro pedido",
        "relacionamento": f"Seu dia fica melhor com {product_name}",
    }
    headline = headlines.get(goal, headlines["promocao"])

    return (
        f"Campanha para {channel}\n\n"
        f"**Chamada principal:** {headline}\n\n"
        f"**Ideia de imagem:** foto clara de {product_name}, produto em destaque e CTA visivel.\n\n"
        f"**Legenda:** Hoje e um bom dia para garantir {product_name}. "
        f"Margem estimada de R$ {margin:.2f} por unidade.\n\n"
        f"**CTA:** Chame no direct ou finalize pelo PIX."
    )
