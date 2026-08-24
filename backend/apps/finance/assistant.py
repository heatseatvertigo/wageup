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
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.finance.insights import brl, gather_metrics
from apps.finance.models import Transaction
from apps.payments.models import Payment
from apps.products.models import Product

MONTHS_PT = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]

MAX_HISTORY = 12          # mensagens da conversa enviadas ao modelo
MAX_MESSAGE_CHARS = 2000  # tamanho máximo de cada mensagem do usuário
RECENT_LIMIT = 15         # movimentações recentes incluídas no contexto
CHARGES_LIMIT = 10        # cobranças PIX recentes incluídas no contexto

SYSTEM_PROMPT = (
    "Você é o assistente financeiro do WageUp. Conversa com donos de negócios "
    "pequenos: confeiteiras, barbeiros, quem vende marmita, quem faz unha. "
    "Gente que entende do próprio ofício, não de contabilidade.\n\n"
    "COMO FALAR:\n"
    "- Fale como um amigo que entende de dinheiro, não como um banco. "
    "Perto, direto, sem cerimônia.\n"
    "- Zero jargão. Nunca diga fluxo de caixa, capital de giro, margem "
    "operacional ou ticket médio. Diga o que sobrou, o dinheiro parado, "
    "quanto rende cada venda.\n"
    "- Use comparações do dia a dia quando ajudar a entender: 'é como se "
    "cada bolo vendido deixasse R$ 12 no bolso'.\n"
    "- Comece pela resposta. Nada de introduções como 'Ótima pergunta!' ou "
    "'Vamos analisar seus dados'.\n"
    "- Três ou quatro frases bastam. Se quiser mais, o usuário pergunta.\n"
    "- Termine sugerindo um próximo passo concreto quando fizer sentido — "
    "algo que a pessoa possa fazer hoje.\n"
    "- Texto corrido, SEM markdown: nada de **negrito**, listas com "
    "asteriscos ou títulos com #.\n\n"
    "REGRAS QUE NÃO SE QUEBRAM:\n"
    "- Use APENAS os números do contexto. Nunca invente valores.\n"
    "- Os números já vêm calculados. Não refaça contas nem some transações.\n"
    "- Se o dado não estiver no contexto, diga com franqueza que ainda não "
    "tem essa informação e explique o que a pessoa pode registrar para "
    "passar a ter.\n"
    "- Você lê números e aponta caminhos. Não é contador: para imposto, "
    "nota fiscal ou declaração, oriente a procurar um profissional.\n"
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


CHARGE_STATUS_PT = {
    "pending": "pendente",
    "paid": "paga",
    "expired": "expirada",
    "canceled": "cancelada",
    "refunded": "reembolsada",
    "failed": "falhou",
}


def pix_charges(business):
    """Cobranças PIX do negócio: totais por status e as mais recentes.

    Só o nome do cliente entra no contexto. CPF, e-mail e celular ficam de
    fora: não ajudam na análise e não há motivo para enviá-los ao provedor.
    """
    charges = Payment.objects.filter(business=business).order_by("-created_at")

    by_status = {}
    for row in charges.values("status").annotate(total=Sum("amount"), count=Count("id")):
        by_status[row["status"]] = {
            "count": row["count"],
            "total": float(row["total"] or 0),
        }

    recent = []
    for charge in charges[:CHARGES_LIMIT]:
        metadata = charge.metadata or {}
        created = timezone.localtime(charge.created_at) if charge.created_at else None
        recent.append({
            "description": metadata.get("description") or "Cobrança PIX",
            "amount": float(charge.amount),
            "status": CHARGE_STATUS_PT.get(charge.status, charge.status),
            "datetime": created.strftime("%d/%m/%Y às %H:%M") if created else "",
            "customer": (metadata.get("customer") or {}).get("name") or "",
        })

    return {"by_status": by_status, "recent": recent, "total_count": charges.count()}


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
        "pix": pix_charges(business),
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

    pix = context["pix"]
    lines.append("")
    lines.append(
        "COBRANÇAS PIX — atenção: uma cobrança paga vira automaticamente uma "
        "entrada no financeiro, então o valor recebido via PIX JÁ ESTÁ contado "
        "dentro das entradas acima. Nunca some os dois."
    )
    lines.append(f"Total de cobranças: {pix['total_count']}")
    if pix["by_status"]:
        for status_key, data in pix["by_status"].items():
            rotulo = CHARGE_STATUS_PT.get(status_key, status_key)
            lines.append(f"- {rotulo}: {data['count']} cobrança(s), {brl(data['total'])}")
    else:
        lines.append("- Nenhuma cobrança gerada ainda.")

    if pix["recent"]:
        lines.append("")
        lines.append("COBRANÇAS PIX RECENTES (data e hora de criação):")
        for item in pix["recent"]:
            cliente = f", cliente {item['customer']}" if item["customer"] else ", sem cliente informado"
            lines.append(
                f"- {item['datetime']}: {item['description']} — {brl(item['amount'])}, "
                f"{item['status']}{cliente}"
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
