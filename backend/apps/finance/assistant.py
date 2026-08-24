"""Assistente financeiro: monta o contexto do negócio e conversa com a IA.

Princípio central: todo número é calculado aqui, em Python. O modelo recebe os
valores prontos e apenas interpreta. LLM erra aritmética silenciosamente, e num
app financeiro um centavo errado é um bug que o usuário não percebe.

Provedores: DeepSeek quando DEEPSEEK_API_KEY existe, Claude como alternativa
quando só ANTHROPIC_API_KEY está configurada, e uma resposta local honesta
quando nenhuma chave existe — assim o app não quebra em desenvolvimento.
"""
from datetime import date

import requests
from django.conf import settings
from django.db.models import Sum
from django.db.models.functions import TruncMonth

from apps.finance.insights import brl, gather_metrics
from apps.finance.models import Transaction
from apps.products.models import Product

MONTHS_PT = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]

MAX_HISTORY = 12          # mensagens da conversa enviadas ao modelo
MAX_MESSAGE_CHARS = 2000  # tamanho máximo de cada mensagem do usuário
RECENT_LIMIT = 15         # movimentações recentes incluídas no contexto

SYSTEM_PROMPT = (
    "Você é o assistente financeiro do WageUp, uma plataforma para "
    "microempreendedores brasileiros.\n\n"
    "REGRAS:\n"
    "- Use APENAS os números fornecidos no contexto. Nunca invente valores.\n"
    "- Os números já vêm calculados. Não refaça contas nem some transações.\n"
    "- Se um dado não estiver no contexto, diga que ainda não tem essa "
    "informação e sugira o que o usuário pode registrar para obtê-la.\n"
    "- Responda em português brasileiro, direto e sem jargão. O usuário não é "
    "contador: fale como alguém explicando para um dono de negócio pequeno.\n"
    "- Seja conciso: no máximo 5 frases, salvo se pedirem detalhamento.\n"
    "- Escreva em texto corrido, SEM markdown: nada de **negrito**, listas com "
    "asteriscos ou títulos com #. A interface exibe texto puro.\n"
    "- Você analisa métricas do negócio e sugere caminhos. Você NÃO é contador "
    "nem consultor tributário: para decisões fiscais, oriente a procurar um "
    "profissional.\n"
)


class AssistantError(Exception):
    pass


def _month_label(value):
    return f"{MONTHS_PT[value.month - 1]}/{value.year}"


def monthly_series(business, months=6):
    """Entradas e saídas por mês, dos últimos N meses."""
    rows = (
        Transaction.objects.filter(business=business)
        .annotate(month=TruncMonth("occurred_at"))
        .values("month", "type")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )

    buckets = {}
    for row in rows:
        if not row["month"]:
            continue
        key = (row["month"].year, row["month"].month)
        bucket = buckets.setdefault(key, {"income": 0.0, "expense": 0.0})
        bucket[row["type"]] = float(row["total"] or 0)

    today = date.today()
    series = []
    for offset in range(months - 1, -1, -1):
        month_index = today.month - offset
        year = today.year + (month_index - 1) // 12
        month = (month_index - 1) % 12 + 1
        bucket = buckets.get((year, month), {"income": 0.0, "expense": 0.0})
        series.append({
            "label": _month_label(date(year, month, 1)),
            "income": bucket["income"],
            "expense": bucket["expense"],
            "profit": bucket["income"] - bucket["expense"],
        })
    return series


def build_context(business):
    """Reúne o retrato financeiro do negócio que vai no prompt."""
    metrics = gather_metrics(business)
    series = monthly_series(business)

    products = sorted(
        Product.objects.filter(business=business),
        key=lambda item: float(item.price) - float(item.cost),
        reverse=True,
    )[:5]

    recent = Transaction.objects.filter(business=business).order_by("-occurred_at")[:RECENT_LIMIT]

    return {
        "business_name": business.name,
        "metrics": metrics,
        "series": series,
        "top_products": [
            {
                "name": item.name,
                "price": float(item.price),
                "cost": float(item.cost),
                "margin": float(item.price) - float(item.cost),
                "stock": item.stock,
            }
            for item in products
        ],
        "recent": [
            {
                "description": item.description,
                "type": item.type,
                "amount": float(item.amount),
                "date": item.occurred_at.strftime("%d/%m/%Y") if item.occurred_at else "",
            }
            for item in recent
        ],
    }


def format_context(context):
    """Transforma o contexto em texto para o prompt."""
    metrics = context["metrics"]
    lines = [
        f"NEGÓCIO: {context['business_name']}",
        "",
        "TOTAIS ACUMULADOS:",
        f"- Entradas: {brl(metrics['income'])}",
        f"- Saídas: {brl(metrics['expense'])}",
        f"- Lucro: {brl(metrics['profit'])}",
        f"- Recebido via PIX: {brl(metrics['received'])}",
        f"- A receber (PIX pendente): {brl(metrics['pending'])}",
        "",
        "ÚLTIMOS 6 MESES:",
    ]
    for item in context["series"]:
        lines.append(
            f"- {item['label']}: entradas {brl(item['income'])}, "
            f"saídas {brl(item['expense'])}, lucro {brl(item['profit'])}"
        )

    lines.append("")
    lines.append(
        f"PRODUTOS ({metrics['product_count']} cadastrados, "
        f"{metrics['low_stock_count']} com estoque baixo):"
    )
    if context["top_products"]:
        for item in context["top_products"]:
            lines.append(
                f"- {item['name']}: preço {brl(item['price'])}, "
                f"custo {brl(item['cost'])}, margem {brl(item['margin'])}, "
                f"estoque {item['stock']}"
            )
    else:
        lines.append("- Nenhum produto cadastrado.")

    lines.append("")
    lines.append("MOVIMENTAÇÕES RECENTES:")
    if context["recent"]:
        for item in context["recent"]:
            kind = "entrada" if item["type"] == "income" else "saída"
            lines.append(
                f"- {item['date']} {kind}: {item['description']} — {brl(item['amount'])}"
            )
    else:
        lines.append("- Nenhuma movimentação registrada.")

    return "\n".join(lines)


def sanitize_history(messages):
    """Valida e limita o histórico recebido do frontend."""
    clean = []
    for item in messages or []:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = str(item.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        clean.append({"role": role, "content": content[:MAX_MESSAGE_CHARS]})
    return clean[-MAX_HISTORY:]


def ask_assistant(business, messages):
    """Devolve (provider, resposta) para a conversa recebida."""
    history = sanitize_history(messages)
    if not history:
        raise AssistantError("Envie uma pergunta.")

    context_text = format_context(build_context(business))
    system_prompt = f"{SYSTEM_PROMPT}\nCONTEXTO ATUAL DO NEGÓCIO:\n{context_text}"

    if settings.DEEPSEEK_API_KEY:
        return "deepseek", _call_deepseek(system_prompt, history)
    if settings.ANTHROPIC_API_KEY:
        return "anthropic", _call_claude(system_prompt, history)
    return "local-demo", _local_answer()


def _call_deepseek(system_prompt, history):
    """A API da DeepSeek segue o formato da OpenAI, entao requests basta."""
    try:
        response = requests.post(
            f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.DEEPSEEK_MODEL,
                "messages": [{"role": "system", "content": system_prompt}, *history],
                "max_tokens": 700,
                "temperature": 0.3,
            },
            timeout=45,
        )
    except requests.Timeout as exc:
        raise AssistantError("O assistente demorou para responder. Tente de novo.") from exc
    except requests.RequestException as exc:
        raise AssistantError(f"Falha de conexao com o assistente: {exc}") from exc

    try:
        body = response.json()
    except ValueError as exc:
        raise AssistantError("Resposta invalida do assistente.") from exc

    if response.status_code >= 400:
        detail = (body.get("error") or {}).get("message") or body
        raise AssistantError(str(detail))

    try:
        return body["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, AttributeError, TypeError) as exc:
        raise AssistantError("Resposta invalida do assistente.") from exc


def _call_claude(system_prompt, history):
    import anthropic as anthropic_sdk

    client = anthropic_sdk.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=700,
        system=system_prompt,
        messages=history,
    )
    return message.content[0].text.strip()


def _local_answer():
    """Sem chave configurada: responde com honestidade, sem fingir IA."""
    return (
        "O assistente de IA ainda não está configurado neste ambiente "
        "(falta a chave DEEPSEEK_API_KEY). Enquanto isso, seus números estão "
        "na Visão geral e nas Movimentações."
    )
