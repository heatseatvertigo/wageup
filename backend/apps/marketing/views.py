from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import MarketingCampaign
from .serializers import MarketingCampaignSerializer


class MarketingCampaignViewSet(viewsets.ModelViewSet):
    queryset = MarketingCampaign.objects.all()
    serializer_class = MarketingCampaignSerializer


@api_view(["POST"])
def marketing_chat(request):
    product = request.data.get("product") or {}
    goal = request.data.get("goal") or "promocao"
    channel = request.data.get("channel") or "Instagram"
    prompt = request.data.get("prompt") or "criar uma campanha rapida"

    product_name = product.get("name") or "seu produto"
    price = float(product.get("price") or 0)
    cost = float(product.get("cost") or 0)
    margin = max(price - cost, 0)

    campaign = MarketingCampaign.objects.create(
        prompt=prompt,
        channel=channel,
        goal=goal,
        status=MarketingCampaign.Status.COMPLETED,
        generated_text=build_demo_campaign(product_name, goal, channel, margin),
        provider="local-demo",
        metadata={"source": "sync-demo"},
    )

    return Response(
        {
            "campaign_id": str(campaign.id),
            "message": campaign.generated_text,
            "image_label": f"{product_name}\n{channel}",
        },
        status=status.HTTP_201_CREATED,
    )


def build_demo_campaign(product_name, goal, channel, margin):
    headlines = {
        "promocao": f"{product_name} com oferta especial por tempo limitado",
        "lancamento": f"Chegou {product_name}: feito para encantar no primeiro pedido",
        "relacionamento": f"Seu dia fica melhor com {product_name}",
    }
    headline = headlines.get(goal, headlines["promocao"])

    return (
        f"Campanha para {channel}\n\n"
        f"Chamada: {headline}\n\n"
        f"Ideia de imagem: foto clara de {product_name}, produto em destaque e CTA visivel.\n\n"
        f"Legenda: Hoje e um bom dia para garantir {product_name}. "
        f"Margem estimada de R$ {margin:.2f} por unidade.\n\n"
        "CTA: Chame no direct ou finalize pelo PIX."
    )

# Create your views here.
