"""Meta de faturamento do mes: quanto entrou, quanto falta e o ritmo.

Um lugar so para a conta, usado pela rota da meta, pelos insights e pelo
assistente. Se cada um somasse do seu jeito, o card diria "faltam R$ 120" e o
assistente outro valor.
"""
import calendar
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.sales.services import intervalo_do_mes

from .models import Goal, Transaction


def faturamento_do_mes(business, ano, mes):
    """Soma das entradas do mes no financeiro: venda, PIX, manual e extrato."""
    inicio, fim = intervalo_do_mes(ano, mes)
    total = Transaction.objects.filter(
        business=business,
        type=Transaction.TransactionType.INCOME,
        occurred_at__gte=inicio,
        occurred_at__lt=fim,
    ).aggregate(t=Sum("amount"))["t"]
    return total or Decimal("0.00")


def progresso_da_meta(business, ano, mes):
    """Situacao da meta do mes, ou None quando o mes nao tem meta."""
    goal = Goal.objects.filter(business=business, month=date(ano, mes, 1)).first()
    if not goal:
        return None

    alvo = goal.target_amount
    feito = faturamento_do_mes(business, ano, mes)
    falta = max(alvo - feito, Decimal("0.00"))
    percentual = (feito / alvo * 100) if alvo > 0 else Decimal("0")

    # Dias que sobram contando hoje. Mes passado tem 0; mes futuro, todos.
    hoje = timezone.localdate()
    dias_no_mes = calendar.monthrange(ano, mes)[1]
    if (ano, mes) < (hoje.year, hoje.month):
        dias_restantes = 0
    elif (ano, mes) > (hoje.year, hoje.month):
        dias_restantes = dias_no_mes
    else:
        dias_restantes = dias_no_mes - hoje.day + 1

    # Quanto precisa entrar por dia daqui ate o fim do mes para bater a meta.
    por_dia = (falta / dias_restantes) if dias_restantes and falta > 0 else Decimal("0.00")

    return {
        "month": f"{ano:04d}-{mes:02d}",
        "target": alvo.quantize(Decimal("0.01")),
        "achieved": feito.quantize(Decimal("0.01")),
        "remaining": falta.quantize(Decimal("0.01")),
        "percent": float(round(percentual, 1)),
        "reached": feito >= alvo,
        "days_left": dias_restantes,
        "needed_per_day": por_dia.quantize(Decimal("0.01")),
    }
