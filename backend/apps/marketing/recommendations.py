"""Recomendacoes de acoes de marketing a partir do desempenho do negocio.

Item do escopo do TCC. A diferenca em relacao aos insights do dashboard
(apps/finance/insights.py) e o que se faz com a resposta: la o usuario le um
diagnostico, aqui cada recomendacao ja vem com produto, canal e objetivo
preenchidos, prontos para virar campanha num clique.

Mesmo padrao dos outros pontos de IA do projeto: Claude Haiku quando ha
ANTHROPIC_API_KEY, regras locais quando nao ha ou quando a chamada falha. A
tela nunca fica vazia por causa de configuracao.

As recomendacoes saem dos numeros do `Product` — `margin_value`,
`margin_percent`, `is_low_stock` — e nao de preco menos custo: divulgar o
produto de margem aparente e mandar o MEI vender o que menos rende.
"""
import json
import logging
import re
from collections import Counter

from datetime import timedelta

import anthropic as anthropic_sdk
from django.conf import settings
from django.utils import timezone

from apps.finance.insights import brl
from apps.products.models import Product
from apps.sales.models import Sale
from apps.sales.services import intervalo_do_mes, resumo_vendas
from .models import MarketingCampaign

# Janela para "produto parado": vendeu nada nesse periodo, embora o negocio
# tenha vendido outras coisas.
DIAS_SEM_VENDA = 30

# "Vendas caindo": compara as unidades dos ultimos 7 dias com as dos 7 dias
# anteriores. Pede um volume minimo na semana anterior para uma venda a menos
# num produto que vende pouco nao virar alarme.
JANELA_QUEDA_DIAS = 7
QUEDA_MINIMA = 0.3
VOLUME_MINIMO_QUEDA = 3

logger = logging.getLogger(__name__)

# Canais que o formulario de campanha oferece. A IA recebe esta lista para nao
# recomendar um canal que a tela nao sabe preencher.
CANAIS = ["Instagram", "WhatsApp", "TikTok"]
OBJETIVOS = {
    "promocao": "promoção / oferta especial",
    "lancamento": "lançamento de produto",
    "relacionamento": "relacionamento com clientes",
}

# Quantos produtos entram no prompt. O catalogo de um MEI e pequeno, mas o
# limite evita mandar centenas de linhas para a IA e pagar por isso.
MAX_PRODUTOS_NO_PROMPT = 12


def gather_signals(business):
    """Os sinais do catalogo que motivam uma acao de marketing."""
    produtos = list(Product.objects.filter(business=business))
    ativos = [p for p in produtos if p.is_active]

    # Produto que nunca teve campanha: divulgar o que ja foi divulgado tres
    # vezes rende menos que estrear o que nunca saiu.
    ja_divulgados = set(
        MarketingCampaign.objects.filter(business=business, product__isnull=False)
        .values_list("product_id", flat=True)
    )

    # Vendas recentes por produto. So conta como "parado" quando o negocio
    # registra vendas: sem nenhuma, todo produto pareceria parado.
    desde = timezone.now() - timedelta(days=DIAS_SEM_VENDA)
    vendidos = set(
        Sale.objects.filter(business=business, status=Sale.Status.DONE, occurred_at__gte=desde)
        .values_list("product_id", flat=True)
    )
    registra_vendas = bool(vendidos)

    # Unidades por produto nas duas ultimas semanas, para achar quem caiu.
    agora = timezone.now()
    semana = timedelta(days=JANELA_QUEDA_DIAS)
    recente, anterior = Counter(), Counter()
    for produto_id, quantidade, quando in Sale.objects.filter(
        business=business, status=Sale.Status.DONE, product__isnull=False,
        occurred_at__gte=agora - 2 * semana, occurred_at__lte=agora,
    ).values_list("product_id", "quantity", "occurred_at"):
        (recente if quando >= agora - semana else anterior)[produto_id] += quantidade

    def queda(produto):
        antes, depois = anterior[produto.id], recente[produto.id]
        if antes >= VOLUME_MINIMO_QUEDA and depois <= antes * (1 - QUEDA_MINIMA):
            return {"before": antes, "recent": depois}
        return None

    def parado(produto):
        tem_o_que_vender = produto.stock > 0 or produto.unit == Product.Unit.SERVICE
        # Produto cadastrado ha menos de 30 dias ainda nao teve tempo de vender.
        tem_idade = produto.created_at <= desde
        return registra_vendas and tem_o_que_vender and tem_idade and produto.id not in vendidos

    def resumo(produto):
        return {
            "id": str(produto.id),
            "name": produto.name,
            "price": float(produto.price),
            "margin": float(produto.margin_value),
            "margin_percent": float(produto.margin_percent),
            "stock": produto.stock,
            "low_stock": produto.is_low_stock,
            "never_promoted": produto.id not in ja_divulgados,
            "stale": parado(produto),
            "falling": queda(produto),
            # Sem estoque nao se divulga: a campanha geraria pedido sem entrega.
            "has_stock": produto.stock > 0 or produto.unit == Product.Unit.SERVICE,
            "controls_stock": produto.unit != Product.Unit.SERVICE,
        }

    ordenados = sorted(ativos, key=lambda p: p.margin_value, reverse=True)
    return {
        "product_count": len(produtos),
        "active_count": len(ativos),
        "inactive_count": len(produtos) - len(ativos),
        "campaign_count": MarketingCampaign.objects.filter(business=business).count(),
        "products": [resumo(p) for p in ordenados[:MAX_PRODUTOS_NO_PROMPT]],
        "best_margin": resumo(ordenados[0]) if ordenados else None,
        "worst_margin": resumo(ordenados[-1]) if len(ordenados) > 1 else None,
        "never_promoted": [resumo(p) for p in ordenados if p.id not in ja_divulgados][:3],
        "low_stock": [resumo(p) for p in ordenados if p.is_low_stock][:3],
        "negative_margin": [resumo(p) for p in ordenados if p.margin_value < 0][:3],
        "stale": [resumo(p) for p in ordenados if p.margin_value > 0 and parado(p)][:3],
        "falling": [
            resumo(p) for p in ordenados
            if p.margin_value > 0 and queda(p) and (p.stock > 0 or p.unit == Product.Unit.SERVICE)
        ][:3],
        "all_products": [resumo(p) for p in ordenados],
    }


def build_recommendations(business):
    """Devolve (provider, lista de recomendacoes).

    Cada recomendacao tem title, text, product_id, product_name, channel e
    goal — o suficiente para a tela montar o formulario de campanha sem que o
    usuario digite nada.
    """
    sinais = gather_signals(business)

    if not sinais["products"]:
        return "local-demo", _sem_produtos()

    provider, recomendacoes = "local-demo", None
    if settings.ANTHROPIC_API_KEY:
        try:
            provider, recomendacoes = "anthropic", _call_claude(business, sinais)
        except Exception:
            logger.exception("Falha ao gerar recomendações de marketing. Usando as regras locais.")
    if recomendacoes is None:
        provider, recomendacoes = "local-demo", _fallback(sinais)

    # O botao de cada cartao depende da situacao do produto, nao do texto que
    # a IA escreveu: em prejuizo a acao e rever o preco, com estoque baixo e
    # avisar quem ja compra, e so no resto e campanha.
    por_id = {item["id"]: item for item in sinais["all_products"]}
    for recomendacao in recomendacoes:
        produto = por_id.get(recomendacao.get("product_id"))
        recomendacao["action"] = tipo_de_acao(produto, recomendacao.get("goal")) if produto else None
    return provider, recomendacoes


# O que o botao de uma recomendacao ou de um produto faz na tela:
# campaign/launch geram a campanha; whatsapp gera o aviso para o WhatsApp;
# price e stock abrem o cadastro do produto.
ACOES = ("campaign", "launch", "whatsapp", "price", "stock")


def tipo_de_acao(produto, goal=None):
    """A acao certa para o produto, a partir dos numeros dele."""
    if produto["margin"] < 0:
        return "price"
    if not produto["has_stock"]:
        return "stock"
    if produto["low_stock"]:
        return "whatsapp"
    # Vendia e caiu: o produto ja e conhecido, o que traz de volta e oferta.
    if produto.get("falling"):
        return "campaign"
    if goal == "lancamento" or produto["never_promoted"]:
        return "launch"
    return "campaign"


def situacao_dos_produtos(business):
    """Cada produto ativo com as vendas do mes, a situacao e a acao sugerida.

    E a tabela "Seus produtos" da tela de marketing. A situacao segue a
    mesma prioridade das recomendacoes: prejuizo e falta de estoque vem
    antes de qualquer divulgacao.
    """
    sinais = gather_signals(business)
    agora = timezone.localtime()
    resumo = resumo_vendas(business, *intervalo_do_mes(agora.year, agora.month))
    vendas = {item["product_id"]: item for item in resumo["products"]}
    ultimas = {}
    for produto_id, quando in (
        Sale.objects.filter(business=business, status=Sale.Status.DONE, product__isnull=False)
        .order_by("product_id", "-occurred_at")
        .values_list("product_id", "occurred_at")
    ):
        ultimas.setdefault(str(produto_id), quando)

    campeao = max(
        (item for item in vendas.values() if item["profit"] > 0),
        key=lambda item: item["profit"], default=None,
    )

    linhas = []
    for produto in sinais["all_products"]:
        venda = vendas.get(produto["id"])
        ultima = ultimas.get(produto["id"])
        dias = (agora - timezone.localtime(ultima)).days if ultima else None
        if produto["margin"] < 0:
            situacao, tom, prioridade = "Prejuízo", "negative", 0
        elif not produto["has_stock"]:
            situacao, tom, prioridade = "Sem estoque", "warning", 1
        elif produto["low_stock"]:
            situacao, tom, prioridade = "Estoque baixo", "warning", 2
        elif produto["falling"]:
            situacao, tom, prioridade = "Vendas caindo", "warning", 3
        elif produto["stale"]:
            situacao = f"Parado há {dias} dias" if dias is not None else f"Sem venda em {DIAS_SEM_VENDA} dias"
            tom, prioridade = "warning", 3
        elif produto["never_promoted"]:
            situacao, tom, prioridade = "Nunca divulgado", "positive", 4
        elif campeao and campeao["product_id"] == produto["id"]:
            situacao, tom, prioridade = "Em alta", "positive", 5
        else:
            situacao, tom, prioridade = "Vendendo", "neutral", 6
        linhas.append({
            "product_id": produto["id"],
            "name": produto["name"],
            "stock": produto["stock"],
            "controls_stock": produto["controls_stock"],
            "margin": f"{produto['margin']:.2f}",
            "quantity_month": venda["quantity"] if venda else 0,
            "profit_month": str(venda["profit"]) if venda else "0.00",
            "status": situacao,
            "tone": tom,
            "action": tipo_de_acao(produto),
            "_ordem": (prioridade, -produto["margin"]),
        })

    linhas.sort(key=lambda linha: linha.pop("_ordem"))
    return linhas


def _call_claude(business, sinais):
    system_prompt = (
        "Você é um consultor de marketing para microempreendedores brasileiros. "
        "Recomenda ações concretas, uma por produto, sempre justificadas pelos números "
        "do negócio. Responde em português brasileiro, sem jargão."
    )

    linhas = []
    for p in sinais["products"]:
        marcas = []
        if p["never_promoted"]:
            marcas.append("nunca divulgado")
        if p["low_stock"]:
            marcas.append("estoque baixo")
        if p["margin"] < 0:
            marcas.append("PREJUÍZO por unidade")
        if p["stale"]:
            marcas.append(f"sem venda nos últimos {DIAS_SEM_VENDA} dias")
        if p["falling"]:
            marcas.append(
                f"vendas caindo: {p['falling']['before']} un. na semana anterior, "
                f"{p['falling']['recent']} nos últimos {JANELA_QUEDA_DIAS} dias"
            )
        if not p["has_stock"]:
            marcas.append("SEM ESTOQUE")
        sufixo = f" [{', '.join(marcas)}]" if marcas else ""
        linhas.append(
            f"- {p['name']}: preço {brl(p['price'])}, margem real {brl(p['margin'])} "
            f"({p['margin_percent']:.0f}% do preço), estoque {p['stock']}{sufixo}"
        )

    user_message = (
        f"Negócio: '{business.name}'\n"
        f"Produtos ativos: {sinais['active_count']} "
        f"(inativos: {sinais['inactive_count']})\n"
        f"Campanhas já geradas: {sinais['campaign_count']}\n\n"
        f"Catálogo, da melhor para a pior margem:\n" + "\n".join(linhas) + "\n\n"
        f"A margem informada já desconta embalagem, frete, taxa de cartão/PIX e imposto. "
        f"É o que sobra de verdade — use ela, não o preço, para decidir o que vale divulgar.\n\n"
        f"Recomende de 3 a 4 ações de marketing. Priorize: produto de margem alta que nunca "
        f"foi divulgado; produto de margem boa com vendas caindo ou parado, sem venda recente; produto com "
        f"estoque baixo (não vale empurrar volume); produto em "
        f"prejuízo (a ação é rever preço, não divulgar).\n\n"
        f"Responda APENAS com um array JSON válido, no formato:\n"
        f'[{{"title": "...", "text": "...", "product_name": "...", '
        f'"channel": "...", "goal": "..."}}]\n'
        f"- title: no máximo 4 palavras\n"
        f"- text: no máximo 2 frases, citando o número que justifica a ação\n"
        f"- product_name: exatamente como aparece no catálogo acima\n"
        f"- channel: um de {', '.join(CANAIS)}\n"
        f"- goal: um de {', '.join(OBJETIVOS)}"
    )

    client = anthropic_sdk.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=900,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return _parse(message.content[0].text, sinais)


def _parse(raw, sinais):
    """Le o JSON da IA e resolve o produto citado.

    O `product_id` nunca vem do modelo: ele e resolvido pelo nome contra o
    catalogo que foi enviado no prompt. Assim uma alucinacao vira recomendacao
    sem produto vinculado, nunca um id de outro negocio.
    """
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return _fallback(sinais)

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return _fallback(sinais)

    por_nome = {p["name"].casefold(): p for p in sinais["products"]}
    recomendacoes = []
    for item in data:
        if not isinstance(item, dict) or not item.get("title") or not item.get("text"):
            continue
        produto = por_nome.get(str(item.get("product_name", "")).casefold())
        canal = str(item.get("channel") or "").strip()
        objetivo = str(item.get("goal") or "").strip()
        recomendacoes.append({
            "title": str(item["title"]),
            "text": str(item["text"]),
            "product_id": produto["id"] if produto else None,
            "product_name": produto["name"] if produto else None,
            "channel": canal if canal in CANAIS else CANAIS[0],
            "goal": objetivo if objetivo in OBJETIVOS else "promocao",
        })

    return recomendacoes or _fallback(sinais)


def _acao(title, text, produto=None, channel="Instagram", goal="promocao"):
    return {
        "title": title,
        "text": text,
        "product_id": produto["id"] if produto else None,
        "product_name": produto["name"] if produto else None,
        "channel": channel,
        "goal": goal,
    }


def texto_da_queda(produto):
    """Frase da queda de vendas, igual nas recomendacoes e nos insights."""
    queda = produto["falling"]
    return (
        f"{produto['name']} vendeu {queda['before']} na semana anterior e "
        f"{queda['recent']} nos últimos {JANELA_QUEDA_DIAS} dias. Uma promoção curta "
        f"ajuda a recuperar o volume: ele deixa {brl(produto['margin'])} por unidade."
    )


def _sem_produtos():
    return [_acao(
        "Comece pelo catálogo",
        "Não há produto ativo cadastrado. Cadastre um produto com preço e custo "
        "para as recomendações usarem a sua margem real.",
    )]


def _fallback(sinais):
    """Regras locais, na mesma ordem de prioridade que o prompt pede da IA."""
    recomendacoes = []

    for produto in sinais["negative_margin"]:
        recomendacoes.append(_acao(
            "Revise o preço",
            f"{produto['name']} dá prejuízo de {brl(abs(produto['margin']))} por unidade "
            f"depois das taxas. Divulgar agora é vender no vermelho: ajuste o preço primeiro.",
            produto,
            goal="promocao",
        ))

    # Queda de vendas vem antes da estreia: um produto que vendia e parou de
    # vender e o que mais perde dinheiro agora, mesmo nunca tendo tido campanha.
    for produto in sinais["falling"]:
        if any(r["product_id"] == produto["id"] for r in recomendacoes):
            continue
        recomendacoes.append(_acao(
            "Recupere as vendas",
            texto_da_queda(produto),
            produto,
            goal="promocao",
        ))
        break

    melhor = sinais["best_margin"]
    for produto in sinais["never_promoted"]:
        if produto["margin"] <= 0 or produto["low_stock"] or not produto["has_stock"]:
            continue
        if any(r["product_id"] == produto["id"] for r in recomendacoes):
            continue
        # "O que mais rende" so quando e verdade: o primeiro nunca divulgado
        # pode nao ser o de melhor margem, que talvez esteja sem estoque.
        destaque = "é o que mais rende" if melhor and melhor["id"] == produto["id"] else "deixa"
        recomendacoes.append(_acao(
            "Estreie a divulgação",
            f"{produto['name']} nunca teve campanha e {destaque}: "
            f"{brl(produto['margin'])} por unidade ({produto['margin_percent']:.0f}% do preço).",
            produto,
            goal="lancamento",
        ))
        break

    for produto in sinais["stale"]:
        if any(r["product_id"] == produto["id"] for r in recomendacoes):
            continue
        recomendacoes.append(_acao(
            "Tire da prateleira",
            f"{produto['name']} não vendeu nos últimos {DIAS_SEM_VENDA} dias e deixa "
            f"{brl(produto['margin'])} por unidade. Uma oferta curta faz ele girar.",
            produto,
            goal="promocao",
        ))
        break

    for produto in sinais["low_stock"]:
        recomendacoes.append(_acao(
            "Reponha antes de divulgar",
            f"{produto['name']} está com {produto['stock']} em estoque. "
            f"Campanha agora gera pedido que você não entrega.",
            produto,
            goal="relacionamento",
        ))
        break

    if melhor and melhor["margin"] > 0 and melhor["has_stock"] and not any(
        r["product_id"] == melhor["id"] for r in recomendacoes
    ):
        recomendacoes.append(_acao(
            "Priorize o que rende",
            f"{melhor['name']} deixa {brl(melhor['margin'])} por unidade. "
            f"É o produto que mais compensa divulgar.",
            melhor,
        ))

    if sinais["campaign_count"] == 0:
        recomendacoes.append(_acao(
            "Teste um canal",
            "Você ainda não gerou campanha nenhuma. Comece pelo WhatsApp, "
            "onde a conversa com o cliente já existe.",
            melhor,
            channel="WhatsApp",
            goal="relacionamento",
        ))

    return recomendacoes[:4]
