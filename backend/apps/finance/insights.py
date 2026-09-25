"""Geração de insights de negócio cruzando finanças, recebíveis e produtos.

Segue o mesmo padrão do marketing (apps/marketing/views.py): usa o Claude Haiku
quando ANTHROPIC_API_KEY está configurada e cai para regras locais caso contrário.
"""
import json
import re

from django.conf import settings
from django.db.models import Sum

from apps.finance.models import Transaction
from apps.payments.models import Payment
from apps.products.models import Product

# Usado so para o produto que ficou sem `min_stock` definido: sem um limite
# proprio, "estoque baixo" precisa de algum ponto de corte.
LOW_STOCK_FALLBACK = 8


def brl(value):
    """Formata um número como moeda brasileira: 1234.56 -> 'R$ 1.234,56'."""
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gather_metrics(business):
    """Agrega os indicadores do negócio usados para gerar insights."""
    txns = Transaction.objects.filter(business=business)
    income = txns.filter(type=Transaction.TransactionType.INCOME).aggregate(t=Sum("amount"))["t"] or 0
    expense = txns.filter(type=Transaction.TransactionType.EXPENSE).aggregate(t=Sum("amount"))["t"] or 0

    payments = Payment.objects.filter(business=business)
    received = payments.filter(status=Payment.Status.PAID).aggregate(t=Sum("amount"))["t"] or 0
    pending = payments.filter(status=Payment.Status.PENDING).aggregate(t=Sum("amount"))["t"] or 0

    products = list(Product.objects.filter(business=business))
    # `is_low_stock` respeita o min_stock que o dono cadastrou; o limite fixo
    # entra so quando ele nao definiu nenhum.
    low_stock = [
        p for p in products
        if p.is_low_stock or (p.min_stock == 0 and p.stock <= LOW_STOCK_FALLBACK)
    ]
    # margin_value desconta outros custos, taxa e imposto. Ordenar por
    # preco menos custo elegeria como "melhor margem" um produto que, depois
    # das taxas, rende menos que outro.
    best_margin = max(products, key=lambda p: p.margin_value, default=None)

    return {
        "income": float(income),
        "expense": float(expense),
        "profit": float(income) - float(expense),
        "received": float(received),
        "pending": float(pending),
        "product_count": len(products),
        "low_stock_count": len(low_stock),
        "low_stock_names": [p.name for p in low_stock[:5]],
        "best_margin_name": best_margin.name if best_margin else None,
        "best_margin_value": float(best_margin.margin_value) if best_margin else 0.0,
    }


def build_insights(business):
    """Retorna (provider, insights) onde insights é uma lista de {title, text}."""
    metrics = gather_metrics(business)

    if settings.ANTHROPIC_API_KEY:
        try:
            return "anthropic", _call_claude(business, metrics)
        except Exception:
            # Se a IA falhar por qualquer motivo, não deixa a tela sem insights.
            return "local-demo", _fallback_insights(metrics)
    return "local-demo", _fallback_insights(metrics)


def _call_claude(business, m):
    import anthropic as anthropic_sdk

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

    user_message = (
        f"Dados do negócio '{business.name}':\n"
        f"- Receita (entradas): {brl(m['income'])}\n"
        f"- Despesas (saídas): {brl(m['expense'])}\n"
        f"- Lucro estimado: {brl(m['profit'])}\n"
        f"- Já recebido via PIX: {brl(m['received'])}\n"
        f"- A receber (PIX pendente): {brl(m['pending'])}\n"
        f"- Produtos cadastrados: {m['product_count']}\n"
        f"- Produtos com estoque baixo: {m['low_stock_count']} ({low_stock})\n"
        f"- Produto de melhor margem: {best_margin}\n\n"
        "Gere de 3 a 4 insights acionáveis. Responda APENAS com um array JSON válido, "
        'no formato [{"title": "...", "text": "..."}]. '
        "O title deve ter no máximo 4 palavras; o text, no máximo 2 frases."
    )

    client = anthropic_sdk.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=700,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    raw = message.content[0].text
    return _parse_insights(raw, m)


def _parse_insights(raw, metrics):
    """Extrai a lista de insights do texto do Claude, com fallback defensivo."""
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            insights = [
                {"title": str(item["title"]), "text": str(item["text"])}
                for item in data
                if isinstance(item, dict) and item.get("title") and item.get("text")
            ]
            if insights:
                return insights
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    # Não conseguiu estruturar: usa regras locais para não deixar a tela vazia.
    return _fallback_insights(metrics)


def _fallback_insights(m):
    insights = []

    if m["income"] > m["expense"]:
        insights.append({
            "title": "Saúde financeira",
            "text": f"Positivo em {brl(m['profit'])}. Mantenha o controle das saídas.",
        })
    elif m["income"] == 0:
        insights.append({
            "title": "Saúde financeira",
            "text": "Nenhuma entrada registrada ainda. Comece lançando suas vendas.",
        })
    else:
        insights.append({
            "title": "Saúde financeira",
            "text": f"Saídas acima das entradas ({brl(m['expense'])} vs {brl(m['income'])}). Reveja os custos.",
        })

    if m["pending"] > 0:
        insights.append({
            "title": "Recebíveis",
            "text": f"Você tem {brl(m['pending'])} a receber. Acompanhe as cobranças pendentes.",
        })

    if m["low_stock_count"]:
        insights.append({
            "title": "Estoque",
            "text": f"{m['low_stock_count']} produto(s) precisam de reposição.",
        })
    elif m["product_count"]:
        insights.append({
            "title": "Estoque",
            "text": "Todos os produtos com estoque em dia.",
        })

    if m["best_margin_name"]:
        insights.append({
            "title": "Melhor margem",
            "text": f"{m['best_margin_name']}: {brl(m['best_margin_value'])} por unidade. Priorize a divulgação dele.",
        })
    else:
        insights.append({
            "title": "Produtos",
            "text": "Cadastre produtos para ver margens e recomendações.",
        })

    return insights
