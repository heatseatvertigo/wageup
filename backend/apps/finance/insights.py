"""Geração de insights de negócio cruzando finanças, recebíveis e produtos.

Provedores na mesma ordem do assistente e do chat de marketing: DeepSeek, depois
Claude Haiku (Anthropic), depois regras locais (`consultar_ia`). A tela nunca fica
sem insights por falta de chave ou por falha do provedor.

Os números são do mês corrente, como os cards ao lado. O total acumulado desde o
primeiro lançamento contradizia o "Lucro do mês" na mesma tela.

Um insight que cita um produto traz `action`: o botão leva à ação no marketing
(RF12 do escopo). A ação sai da situação do produto (`tipo_de_acao`), nunca do
texto da IA, como nas recomendações do marketing.
"""
import hashlib
import json
import logging
import re
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Sum
from django.utils import timezone

from apps.finance.models import Transaction
from apps.payments.models import Payment
from apps.products.models import Product
from apps.sales.services import intervalo_do_mes, resumo_vendas

logger = logging.getLogger(__name__)

# Usado so para o produto que ficou sem `min_stock` definido: sem um limite
# proprio, "estoque baixo" precisa de algum ponto de corte.
LOW_STOCK_FALLBACK = 8

MONTHS_PT = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def brl(value):
    """Formata um número como moeda brasileira: 1234.56 -> 'R$ 1.234,56'."""
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _entradas_e_saidas(txns):
    income = txns.filter(type=Transaction.TransactionType.INCOME).aggregate(t=Sum("amount"))["t"] or 0
    expense = txns.filter(type=Transaction.TransactionType.EXPENSE).aggregate(t=Sum("amount"))["t"] or 0
    return float(income), float(expense)


def gather_metrics(business):
    """Agrega os indicadores do negócio usados para gerar insights.

    `income`/`expense`/`profit` são o acumulado (o assistente usa); os
    `month_*` são do mês corrente e `prev_*` do mesmo período do mês
    anterior: no dia 15, do dia 1 ao 15 de lá. Comparar meio mês com o mês
    inteiro diria "50% abaixo" todo dia 15.
    """
    from .goals import progresso_da_meta

    txns = Transaction.objects.filter(business=business)
    income, expense = _entradas_e_saidas(txns)

    agora = timezone.localtime()
    inicio, fim = intervalo_do_mes(agora.year, agora.month)
    month_income, month_expense = _entradas_e_saidas(txns.filter(occurred_at__gte=inicio, occurred_at__lt=fim))
    ano_ant, mes_ant = (agora.year - 1, 12) if agora.month == 1 else (agora.year, agora.month - 1)
    inicio_ant = intervalo_do_mes(ano_ant, mes_ant)[0]
    # Dia inteiro, como a tela: no dia 15, conta até o fim do dia 15 de lá.
    corte = min(inicio_ant + timedelta(days=agora.day), inicio)
    prev_income, prev_expense = _entradas_e_saidas(
        txns.filter(occurred_at__gte=inicio_ant, occurred_at__lt=corte)
    )

    payments = Payment.objects.filter(business=business)
    received = payments.filter(status=Payment.Status.PAID).aggregate(t=Sum("amount"))["t"] or 0
    pending = payments.filter(status=Payment.Status.PENDING).aggregate(t=Sum("amount"))["t"] or 0

    products = list(Product.objects.filter(business=business))
    # `is_low_stock` respeita o min_stock que o dono cadastrou; o limite fixo
    # entra so quando ele nao definiu nenhum.
    # Serviço não tem estoque: com estoque 0, entrava como "precisa repor".
    low_stock = [
        p for p in products
        if p.unit != Product.Unit.SERVICE
        and (p.is_low_stock or (p.min_stock == 0 and p.stock <= LOW_STOCK_FALLBACK))
    ]
    # margin_value desconta outros custos, taxa e imposto. Ordenar por
    # preco menos custo elegeria como "melhor margem" um produto que, depois
    # das taxas, rende menos que outro.
    best_margin = max(products, key=lambda p: p.margin_value, default=None)

    # Lucro realizado no mes, das vendas. A margem do cadastro diz quanto cada
    # unidade pode render; a venda diz quanto rendeu de fato.
    vendas = resumo_vendas(business, *intervalo_do_mes(agora.year, agora.month))
    campeao = vendas["products"][0] if vendas["products"] else None

    return {
        "income": income,
        "expense": expense,
        "profit": income - expense,
        "month_label": MONTHS_PT[agora.month - 1],
        "prev_month_label": MONTHS_PT[mes_ant - 1],
        "month_income": month_income,
        "month_expense": month_expense,
        "month_profit": month_income - month_expense,
        "prev_income": prev_income,
        "prev_profit": prev_income - prev_expense,
        "goal": progresso_da_meta(business, agora.year, agora.month),
        "received": float(received),
        "pending": float(pending),
        "product_count": len(products),
        "low_stock_count": len(low_stock),
        "low_stock_names": [p.name for p in low_stock[:5]],
        "best_margin_name": best_margin.name if best_margin else None,
        "best_margin_value": float(best_margin.margin_value) if best_margin else 0.0,
        "sales_count": vendas["totals"]["count"],
        "sales_total": float(vendas["totals"]["total"]),
        "sales_profit": float(vendas["totals"]["profit"]),
        "top_seller_name": campeao["product_name"] if campeao else None,
        "top_seller_profit": float(campeao["profit"]) if campeao else 0.0,
        "top_seller_quantity": campeao["quantity"] if campeao else 0,
    }


def build_insights(business):
    """Retorna (provider, insights): lista de {title, text, action}.

    `action` é None ou {product_id, product_name, type}, com o tipo de
    `tipo_de_acao` do marketing.
    """
    # Import tardio: o marketing importa `brl` deste módulo.
    from apps.marketing.recommendations import gather_signals

    metrics = gather_metrics(business)
    sinais = gather_signals(business)

    system_prompt, user_message = _prompt_insights(business, metrics, sinais)
    provider, insights = consultar_ia(
        system_prompt, user_message, 700,
        ler=lambda raw: _parse_insights(raw, sinais),
        claude=_call_claude,
    )
    if not insights:
        # Sem chave ou com a IA fora do ar, a tela não fica sem insights.
        provider, insights = "local-demo", _fallback_insights(metrics, sinais)
    return provider, insights


IA_CACHE_SEGUNDOS = 30 * 60


def consultar_ia(system_prompt, user_message, max_tokens, ler, claude):
    """Pede a resposta à DeepSeek e, se falhar ou vier ilegível, à Anthropic.

    `ler` transforma o texto do modelo no resultado (None se não der); `claude`
    é a chamada à Anthropic de quem pede. Devolve (provider, resultado), ou
    (None, None) quando não há chave ou todos falharam: quem chama usa as
    regras locais. Usada também pelas recomendações do marketing.
    """
    # A mesma pergunta com os mesmos números tem a mesma resposta: guarda por
    # meia hora. Sem isto, cada visita à Visão geral esperava a IA de novo, e
    # no servidor de um processo só a espera prendia todas as outras
    # requisições. Número novo (uma venda, uma despesa) muda o prompt e,
    # com ele, a chave.
    chave = "ia:" + hashlib.sha256(
        f"{max_tokens}\x00{system_prompt}\x00{user_message}".encode()
    ).hexdigest()
    guardado = cache.get(chave)
    if guardado:
        return guardado

    provedores = []
    if settings.DEEPSEEK_API_KEY:
        provedores.append(("deepseek", _texto_deepseek))
    if settings.ANTHROPIC_API_KEY:
        provedores.append(("anthropic", claude))
    for nome, chamar in provedores:
        try:
            resultado = ler(chamar(system_prompt, user_message, max_tokens))
        except Exception:
            logger.exception("Falha ao consultar %s. Tentando a próxima opção.", nome)
            continue
        if resultado:
            cache.set(chave, (nome, resultado), IA_CACHE_SEGUNDOS)
            return nome, resultado
    return None, None


def _texto_deepseek(system_prompt, user_message, max_tokens):
    # Import tardio: o assistente importa este módulo.
    from apps.finance.assistant import _call_deepseek

    return _call_deepseek(
        system_prompt, [{"role": "user", "content": user_message}],
        max_tokens=max_tokens, temperature=0.3,
    )


def _acao(produto):
    """A ação do botão para o produto citado no insight."""
    from apps.marketing.recommendations import tipo_de_acao

    if not produto:
        return None
    return {"product_id": produto["id"], "product_name": produto["name"], "type": tipo_de_acao(produto)}


def _variacao(atual, anterior):
    """'12% acima de setembro' — None quando o mês anterior não tem base."""
    if anterior <= 0:
        return None
    diferenca = (atual - anterior) / anterior * 100
    if abs(diferenca) < 1:
        return "igual"
    return f"{abs(diferenca):.0f}% {'acima' if diferenca > 0 else 'abaixo'}"


def _prompt_insights(business, m, sinais):
    from apps.marketing.recommendations import JANELA_QUEDA_DIAS

    system_prompt = (
        "Você é um consultor financeiro para microempreendedores brasileiros. "
        "Analise os dados do negócio e gere observações curtas, concretas e acionáveis. "
        "Responda sempre em português brasileiro, sem jargão corporativo."
    )

    low_stock = ", ".join(m["low_stock_names"]) or "nenhum"
    best_margin = (
        f"{m['best_margin_name']} ({brl(m['best_margin_value'])} por unidade)"
        if m["best_margin_name"] else "nenhum produto cadastrado"
    )

    top_seller = (
        f"{m['top_seller_name']} ({m['top_seller_quantity']} unidade(s), lucro {brl(m['top_seller_profit'])})"
        if m["top_seller_name"] else "nenhuma venda registrada"
    )

    meta = m["goal"]
    linha_meta = (
        f"- Meta de faturamento de {m['month_label']}: {brl(meta['target'])}; "
        f"entrou {brl(meta['achieved'])} ({meta['percent']:.0f}%), faltam {brl(meta['remaining'])} "
        f"em {meta['days_left']} dia(s)\n"
        if meta else f"- Meta de faturamento de {m['month_label']}: não definida\n"
    )
    caindo = "; ".join(
        f"{p['name']} ({p['falling']['before']} un. na semana anterior, "
        f"{p['falling']['recent']} nos últimos {JANELA_QUEDA_DIAS} dias)"
        for p in sinais["falling"]
    ) or "nenhum"

    user_message = (
        f"Dados do negócio '{business.name}' em {m['month_label']}:\n"
        f"- Entradas do mês até hoje: {brl(m['month_income'])} "
        f"(mesmo período de {m['prev_month_label']}: {brl(m['prev_income'])})\n"
        f"- Saídas do mês: {brl(m['month_expense'])}\n"
        f"- Lucro do mês até hoje: {brl(m['month_profit'])} "
        f"(mesmo período de {m['prev_month_label']}: {brl(m['prev_profit'])})\n"
        + linha_meta +
        f"- Já recebido via PIX: {brl(m['received'])}\n"
        f"- A receber (PIX pendente): {brl(m['pending'])}\n"
        f"- Produtos cadastrados: {m['product_count']}\n"
        f"- Produtos com estoque baixo: {m['low_stock_count']} ({low_stock})\n"
        f"- Produto de melhor margem: {best_margin}\n"
        f"- Vendas do mês: {m['sales_count']}, faturamento {brl(m['sales_total'])}, "
        f"lucro realizado {brl(m['sales_profit'])} (já descontados custo, taxa e imposto)\n"
        f"- Produto que mais lucrou no mês: {top_seller}\n"
        f"- Produtos com vendas caindo: {caindo}\n\n"
        "Gere de 3 a 4 insights acionáveis. Fale como parceiro do negócio: "
        "'Você está a R$ 120 da sua meta', não 'meta não atingida'. "
        "Responda APENAS com um array JSON válido, "
        'no formato [{"title": "...", "text": "...", "product_name": "..."}]. '
        "O title deve ter no máximo 4 palavras; o text, no máximo 2 frases. "
        "product_name é o nome exato do produto que o insight cita, ou vazio."
    )

    return system_prompt, user_message


def _call_claude(system_prompt, user_message, max_tokens):
    import anthropic as anthropic_sdk

    client = anthropic_sdk.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text


def _parse_insights(raw, sinais):
    """Extrai a lista de insights do texto do Claude; None se não der.

    O produto é resolvido pelo nome contra o catálogo do próprio negócio: um
    nome inventado vira insight sem botão, nunca um id de outro negócio.
    """
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None

    por_nome = {p["name"].casefold(): p for p in sinais["all_products"]}
    insights = []
    for item in data:
        if not isinstance(item, dict) or not item.get("title") or not item.get("text"):
            continue
        produto = por_nome.get(str(item.get("product_name") or "").strip().casefold())
        insights.append({"title": str(item["title"]), "text": str(item["text"]), "action": _acao(produto)})
    return insights or None


def _fallback_insights(m, sinais):
    from apps.marketing.recommendations import texto_da_queda

    por_id = {p["id"]: p for p in sinais["all_products"]}
    por_nome = {p["name"]: p for p in sinais["all_products"]}
    insights = []

    def add(title, text, produto=None):
        insights.append({"title": title, "text": text, "action": _acao(produto)})

    meta = m["goal"]
    if meta and meta["reached"]:
        add("Meta do mês", f"Meta de {m['month_label']} batida: entrou {brl(meta['achieved'])} de {brl(meta['target'])}.")
    elif meta:
        dias = meta["days_left"]
        ritmo = (
            f" Faltam {dias} dia{'s' if dias != 1 else ''}: dá {brl(meta['needed_per_day'])} por dia."
            if dias else ""
        )
        add("Meta do mês", f"Você está a {brl(meta['remaining'])} da sua meta de {m['month_label']}.{ritmo}")

    variacao = _variacao(m["month_income"], m["prev_income"])
    comparacao = (
        f" Entrou {variacao} do mesmo período de {m['prev_month_label']}." if variacao and variacao != "igual"
        else f" Entrou o mesmo que no mesmo período de {m['prev_month_label']}." if variacao else ""
    )
    if m["month_income"] == 0 and m["month_expense"] == 0:
        add("Saúde do mês", f"Nada lançado em {m['month_label']} ainda. Registre suas vendas para acompanhar o mês.")
    elif m["month_profit"] >= 0:
        add("Saúde do mês", f"Sobrou {brl(m['month_profit'])} em {m['month_label']}.{comparacao}")
    else:
        add(
            "Saúde do mês",
            f"Saiu mais do que entrou em {m['month_label']}: {brl(m['month_expense'])} contra "
            f"{brl(m['month_income'])}. Reveja os custos.{comparacao}",
        )

    if sinais["falling"]:
        produto = sinais["falling"][0]
        add("Vendas caindo", texto_da_queda(produto), produto)

    if m["top_seller_name"]:
        add(
            "Lucro das vendas",
            f"{m['sales_count']} venda(s) no mês deram {brl(m['sales_profit'])} de lucro real. "
            f"{m['top_seller_name']} puxou a fila, com {brl(m['top_seller_profit'])}.",
            por_nome.get(m["top_seller_name"]),
        )

    if m["pending"] > 0:
        add("Recebíveis", f"Você tem {brl(m['pending'])} a receber. Acompanhe as cobranças pendentes.")

    if m["low_stock_count"]:
        baixo = next((por_nome[nome] for nome in m["low_stock_names"] if nome in por_nome), None)
        add("Estoque", f"{m['low_stock_count']} produto(s) precisam de reposição.", baixo)
    elif m["product_count"]:
        add("Estoque", "Todos os produtos com estoque em dia.")

    if m["best_margin_name"]:
        add(
            "Melhor margem",
            f"{m['best_margin_name']}: {brl(m['best_margin_value'])} por unidade. Priorize a divulgação dele.",
            por_nome.get(m["best_margin_name"]),
        )
    else:
        add("Produtos", "Cadastre produtos para ver margens e recomendações.")

    # Produto inativo não está em `sinais`: o insight fica, sem botão. E um
    # produto ganha botão uma vez só: dois botões iguais lado a lado confundem.
    com_botao = set()
    for item in insights:
        acao = item["action"]
        if acao and (acao["product_id"] not in por_id or acao["product_id"] in com_botao):
            item["action"] = None
        elif acao:
            com_botao.add(acao["product_id"])
    return insights
