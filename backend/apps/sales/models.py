import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Sale(models.Model):
    """Uma venda: liga o produto vendido ao estoque e ao financeiro.

    Sem a venda, o catalogo e o financeiro nao se conversavam: a margem
    calculada no produto nunca virava lucro realizado, e vender nao baixava
    o estoque. Os valores do produto sao copiados no momento da venda, porque
    preco e custo mudam depois e o lucro de uma venda antiga nao pode mudar
    junto.
    """

    class PaymentMethod(models.TextChoices):
        PIX = "pix", "PIX"
        CASH = "dinheiro", "Dinheiro"
        CARD = "cartao", "Cartao"
        OTHER = "outro", "Outro"

    class Status(models.TextChoices):
        DONE = "concluida", "Concluida"
        CANCELED = "cancelada", "Cancelada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey("businesses.Business", on_delete=models.CASCADE, related_name="sales")
    # SET_NULL: apagar o produto nao pode apagar a venda nem o lucro dela.
    product = models.ForeignKey(
        "products.Product", on_delete=models.SET_NULL, related_name="sales", null=True, blank=True
    )
    product_name = models.CharField(max_length=160)
    quantity = models.PositiveIntegerField()

    # Copia do produto no momento da venda.
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Resultado, gravado para o resumo nao refazer a conta a cada consulta.
    total = models.DecimalField(max_digits=12, decimal_places=2)
    cost_total = models.DecimalField(max_digits=12, decimal_places=2)
    fees = models.DecimalField(max_digits=12, decimal_places=2)
    profit = models.DecimalField(max_digits=12, decimal_places=2)

    payment_method = models.CharField(max_length=16, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DONE)
    # Unidades que de fato sairam do estoque: servico nao controla estoque, e a
    # venda paga por PIX nao e bloqueada se o estoque acabou no meio do caminho.
    # E o que volta para o estoque se a venda for cancelada.
    stock_moved = models.PositiveIntegerField(default=0)

    transaction = models.OneToOneField(
        "finance.Transaction", on_delete=models.SET_NULL, related_name="sale", null=True, blank=True
    )
    payment = models.OneToOneField(
        "payments.Payment", on_delete=models.SET_NULL, related_name="sale", null=True, blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="+", null=True, blank=True
    )
    occurred_at = models.DateTimeField(default=timezone.now)
    canceled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]

    def __str__(self):
        return f"{self.quantity}x {self.product_name}"
