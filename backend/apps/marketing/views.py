import hashlib
import logging
from decimal import Decimal, InvalidOperation

import anthropic as anthropic_sdk
from django.conf import settings
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.throttles import AIRateThrottle
from apps.businesses.models import Business
from apps.products.models import Product
from .images import extrair_prompt, gerar_imagem
from .models import CampaignImage, MarketingCampaign
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


def _to_decimal(valor):
    """Converte o que veio no corpo da requisicao, sem derrubar a rota.

    O front manda numero, mas o corpo e JSON livre: um "R$ 100,00" digitado
    em qualquer integracao futura virava ValueError e 500. Valor ilegivel
    conta como zero — a campanha sai sem o dado, nao com erro.
    """
    try:
        return Decimal(str(valor or 0))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _dados_do_produto(request, business):
    """Preco, custo e margem do produto, lidos do banco quando possivel.

    O corpo da requisicao traz o id; os numeros vem do `Product`, nunca do
    cliente. Sao duas razoes: a margem do modelo desconta outros custos,
    taxa e imposto (`margin_value`), enquanto preco menos custo engana; e o
    cliente nao deve ditar os numeros que vao para a IA.

    Sem id valido — produto de outro negocio, produto apagado, requisicao
    manual — cai no que veio no corpo, para a campanha continuar saindo.
    """
    payload = request.data.get("product") or {}
    if not isinstance(payload, dict):
        payload = {}

    produto = None
    product_id = payload.get("id")
    if product_id and business:
        # O filtro por business e o que impede pedir campanha com o produto
        # de outra conta.
        produto = Product.objects.filter(id=product_id, business=business).first()

    if produto is not None:
        return produto, {
            "name": produto.name,
            "price": produto.price,
            "cost": produto.variable_cost,
            "margin": produto.margin_value,
            "margin_percent": produto.margin_percent,
            "fees": produto.fee_amount,
        }

    price = _to_decimal(payload.get("price"))
    cost = _to_decimal(payload.get("cost"))
    return None, {
        "name": payload.get("name") or "seu produto",
        "price": price,
        "cost": cost,
        "margin": max(price - cost, Decimal("0")),
        "margin_percent": None,
        "fees": None,
    }


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([AIRateThrottle])
def marketing_chat(request):
    goal = request.data.get("goal") or "promocao"
    channel = request.data.get("channel") or "Instagram"
    prompt = request.data.get("prompt") or "criar uma campanha rapida"

    business = Business.objects.filter(owner=request.user).first()
    business_name = business.name if business else ""

    produto, dados = _dados_do_produto(request, business)
    product_name = dados["name"]
    price = dados["price"]
    cost = dados["cost"]
    margin = dados["margin"]

    generated_text = None
    provider = "local-demo"
    if settings.ANTHROPIC_API_KEY:
        try:
            generated_text = _call_claude(
                dados, goal, channel, prompt, business_name
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
        product=produto,
        prompt=prompt,
        channel=channel,
        goal=goal,
        status=MarketingCampaign.Status.COMPLETED,
        generated_text=generated_text,
        provider=provider,
        metadata={"source": provider},
    )

    tem_imagem = _gerar_imagem_da_campanha(campaign, product_name, channel)

    return Response(
        {
            "campaign_id": str(campaign.id),
            "message": campaign.generated_text,
            "image_label": f"{product_name}\n{channel}",
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


def _call_claude(dados, goal, channel, prompt, business_name):
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

    # A margem aqui e a do modelo: preco menos custo variavel menos taxa e
    # imposto. Mandar preco menos custo faria a IA sugerir desconto sobre um
    # lucro que nao existe.
    linhas_margem = [f"Margem real por unidade: R$ {dados['margin']:.2f}"]
    if dados["margin_percent"] is not None:
        linhas_margem.append(f"Margem sobre o preço: {dados['margin_percent']:.2f}%")
    if dados["fees"] is not None:
        linhas_margem.append(f"Taxa de cartão/PIX e imposto já descontados: R$ {dados['fees']:.2f}")

    user_message = (
        f"Crie uma campanha de marketing para o seguinte contexto:\n\n"
        f"Negócio: {business_name or 'microempreendedor'}\n"
        f"Produto: {dados['name']}\n"
        f"Preço de venda: R$ {dados['price']:.2f}\n"
        f"Custo por unidade (inclui embalagem e frete): R$ {dados['cost']:.2f}\n"
        + "".join(f"{linha}\n" for linha in linhas_margem) +
        f"Objetivo da campanha: {goal_label}\n"
        f"Canal: {channel}\n"
        f"Pedido do usuário: {prompt}\n\n"
        f"Estruture a resposta com:\n"
        f"**Chamada principal:** (headline curta e impactante)\n"
        f"**Ideia de imagem:** (descrição visual objetiva)\n"
        f"**Legenda:** (texto para postar no {channel}, com emojis se fizer sentido)\n"
        f"**CTA:** (chamada para ação direta)\n\n"
        f"Seja direto, não use linguagem corporativa e adapte o tom para o {channel}.\n"
        f"Se sugerir desconto, respeite a margem real informada: um desconto "
        f"maior que ela faz o negócio vender no prejuízo."
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
