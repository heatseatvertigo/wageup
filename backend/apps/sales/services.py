"""Regras da venda: estoque, lucro e lancamento no financeiro.

Ficam aqui, e nao na view, porque a venda nasce por dois caminhos: o registro
na tela de vendas e a cobranca PIX de um produto que acabou de ser paga.
"""
from collections import OrderedDict
from decimal import Decimal

from django.db import transaction as db_transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.utils import timezone

from apps.finance.models import Transaction
from apps.products.models import CEM, CENTAVO, Product

from .models import Sale


class VendaInvalida(Exception):
    """A venda nao pode ser feita. A mensagem vai para o usuario."""


def controla_estoque(produto):
    """Servico nao tem estoque: vender uma consulta nao baixa nada."""
    return produto.unit != Product.Unit.SERVICE


def _valores(produto, quantidade, preco_unitario):
    percentual = (produto.fee_percent or 0) + (produto.tax_percent or 0)
    # Taxa por unidade, arredondada como em Product.fee_amount: vendendo pelo
    # preco de tabela, o lucro da venda e exatamente margin_value * quantidade.
    taxa_unitaria = (preco_unitario * percentual / CEM).quantize(CENTAVO)
    custo_unitario = produto.variable_cost
    total = preco_unitario * quantidade
    custo_total = custo_unitario * quantidade
    taxas = taxa_unitaria * quantidade
    return {
        "unit_price": preco_unitario,
        "unit_cost": custo_unitario,
        "fee_percent": produto.fee_percent or 0,
        "tax_percent": produto.tax_percent or 0,
        "total": total,
        "cost_total": custo_total,
        "fees": taxas,
        "profit": total - custo_total - taxas,
    }


def _descricao(quantidade, nome):
    return f"Venda: {quantidade}x {nome}"[:180]


@db_transaction.atomic
def registrar_venda(*, business, produto, quantidade, payment_method, preco_unitario=None,
                    occurred_at=None, user=None):
    """Registra a venda, baixa o estoque e lanca a entrada no financeiro.

    Estoque insuficiente bloqueia a venda: o numero de estoque so serve se
    nunca mentir. A baixa e um UPDATE condicional, entao duas vendas ao mesmo
    tempo nao levam o estoque abaixo de zero.
    """
    if produto.business_id != business.id:
        raise VendaInvalida("Produto não encontrado.")
    if not produto.is_active:
        raise VendaInvalida("Este produto está inativo. Ative-o antes de vender.")

    preco = produto.price if preco_unitario is None else Decimal(preco_unitario)
    movido = 0
    if controla_estoque(produto):
        baixou = Product.objects.filter(pk=produto.pk, stock__gte=quantidade).update(
            stock=F("stock") - quantidade
        )
        if not baixou:
            produto.refresh_from_db(fields=["stock"])
            raise VendaInvalida(
                f"Só há {produto.stock} em estoque de {produto.name}. "
                "Ajuste o estoque no cadastro do produto se tiver mais."
            )
        movido = quantidade

    quando = occurred_at or timezone.now()
    valores = _valores(produto, quantidade, preco)
    lancamento = Transaction.objects.create(
        business=business,
        description=_descricao(quantidade, produto.name),
        type=Transaction.TransactionType.INCOME,
        amount=valores["total"],
        source=Transaction.Source.SALE,
        payment_method=payment_method,
        occurred_at=quando,
    )
    return Sale.objects.create(
        business=business,
        product=produto,
        product_name=produto.name,
        quantity=quantidade,
        payment_method=payment_method,
        stock_moved=movido,
        transaction=lancamento,
        created_by=user,
        occurred_at=quando,
        **valores,
    )


@db_transaction.atomic
def venda_do_pix(payment, lancamento):
    """Transforma em venda a cobranca PIX de um produto que acabou de ser paga.

    O dinheiro ja entrou, entao aqui o estoque nao bloqueia: baixa ate zero.
    A entrada no financeiro ja foi criada pela conciliacao do PIX e e so
    ligada a venda. Idempotente: a mesma cobranca nunca gera duas vendas.
    """
    produto_id = (payment.metadata or {}).get("product_id")
    if not produto_id or not payment.business_id or Sale.objects.filter(payment=payment).exists():
        return None
    produto = Product.objects.filter(pk=produto_id, business_id=payment.business_id).first()
    if produto is None:
        return None

    quantidade = int(payment.metadata.get("quantity") or 1)
    movido = 0
    if controla_estoque(produto):
        produto.refresh_from_db(fields=["stock"])
        movido = min(produto.stock, quantidade)
        Product.objects.filter(pk=produto.pk).update(
            stock=Greatest(F("stock") - quantidade, Value(0))
        )

    preco_unitario = (payment.amount / quantidade).quantize(CENTAVO)
    return Sale.objects.create(
        business_id=payment.business_id,
        product=produto,
        product_name=produto.name,
        quantity=quantidade,
        payment_method=Sale.PaymentMethod.PIX,
        stock_moved=movido,
        transaction=lancamento,
        payment=payment,
        **_valores(produto, quantidade, preco_unitario),
    )


@db_transaction.atomic
def cancelar_venda(venda, *, apagar_lancamento=True):
    """Cancela a venda e devolve ao estoque o que tinha saido.

    Venda registrada na tela: o lancamento de entrada e apagado, porque a
    venda nao aconteceu. Venda de PIX estornado: o lancamento fica, e o
    estorno ja lancou a saida correspondente.
    """
    if venda.status == Sale.Status.CANCELED:
        return venda
    if venda.stock_moved and venda.product_id:
        Product.objects.filter(pk=venda.product_id).update(stock=F("stock") + venda.stock_moved)
    if apagar_lancamento and venda.transaction_id:
        Transaction.objects.filter(pk=venda.transaction_id, source=Transaction.Source.SALE).delete()
    venda.status = Sale.Status.CANCELED
    venda.canceled_at = timezone.now()
    venda.save(update_fields=["status", "canceled_at"])
    return venda


def intervalo_do_mes(ano, mes):
    """Inicio e fim do mes no fuso do projeto."""
    inicio = timezone.make_aware(timezone.datetime(ano, mes, 1))
    fim = timezone.make_aware(timezone.datetime(ano + (mes == 12), mes % 12 + 1, 1))
    return inicio, fim


def resumo_vendas(business, inicio, fim):
    """Lucro realizado por produto no periodo, do que mais lucrou ao que menos."""
    vendas = Sale.objects.filter(
        business=business, status=Sale.Status.DONE, occurred_at__gte=inicio, occurred_at__lt=fim
    )
    por_produto = OrderedDict()
    zero = Decimal("0.00")
    totais = {"quantity": 0, "total": zero, "cost_total": zero, "fees": zero, "profit": zero, "count": 0}
    for venda in vendas:
        chave = str(venda.product_id or venda.product_name)
        item = por_produto.setdefault(chave, {
            "product_id": str(venda.product_id) if venda.product_id else None,
            "product_name": venda.product_name,
            "quantity": 0, "total": zero, "cost_total": zero, "fees": zero, "profit": zero, "count": 0,
        })
        for alvo in (item, totais):
            alvo["quantity"] += venda.quantity
            alvo["total"] += venda.total
            alvo["cost_total"] += venda.cost_total
            alvo["fees"] += venda.fees
            alvo["profit"] += venda.profit
            alvo["count"] += 1
    produtos = sorted(por_produto.values(), key=lambda item: item["profit"], reverse=True)
    return {"totals": totais, "products": produtos}
