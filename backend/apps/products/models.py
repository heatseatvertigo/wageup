from decimal import Decimal

from django.db import models
import uuid

CEM = Decimal("100")
CENTAVO = Decimal("0.01")


class Product(models.Model):
    """Um item do catalogo, com o que o calculo de margem precisa.

    Custo e preco sozinhos dao margem bruta, que engana: a taxa da maquininha e
    o imposto saem do mesmo bolso e nao aparecem nessa conta. Os campos de
    percentual existem para a margem exibida ser a que sobra de verdade.
    """

    class Unit(models.TextChoices):
        UNIT = "un", "Unidade"
        KG = "kg", "Quilograma"
        G = "g", "Grama"
        L = "l", "Litro"
        ML = "ml", "Mililitro"
        M = "m", "Metro"
        PACK = "pct", "Pacote"
        SERVICE = "srv", "Servico"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="products",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=160)
    sku = models.CharField(max_length=60, blank=True, default="")
    category = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True, default="")
    unit = models.CharField(max_length=8, choices=Unit.choices, default=Unit.UNIT)

    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Embalagem, frete, etiqueta: custo por unidade vendida que some da conta
    # quando so existe "custo" e o MEI acha que a margem e maior do que e.
    other_costs = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Percentuais incidem sobre o preco de venda, nao sobre o custo.
    fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    stock = models.PositiveIntegerField(default=0)
    min_stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    # ------------------------------------------------------------------
    # Calculo de margem. Fica aqui para existir uma verdade so: o serializer
    # expoe estes valores e a tela repete a formula apenas para dar retorno ao
    # vivo enquanto o usuario digita.
    # ------------------------------------------------------------------

    @property
    def variable_cost(self):
        """O que sai do bolso por unidade vendida, sem contar percentuais."""
        return (self.cost or 0) + (self.other_costs or 0)

    @property
    def fee_amount(self):
        """Taxa e imposto em reais, calculados sobre o preco de venda."""
        percentual = (self.fee_percent or 0) + (self.tax_percent or 0)
        return ((self.price or 0) * percentual / CEM).quantize(CENTAVO)

    @property
    def margin_value(self):
        return ((self.price or 0) - self.variable_cost - self.fee_amount).quantize(CENTAVO)

    @property
    def margin_percent(self):
        """Quanto do preco de venda sobra. E o numero que o MEI precisa ver."""
        if not self.price:
            return Decimal("0.00")
        return (self.margin_value / self.price * CEM).quantize(CENTAVO)

    @property
    def markup_percent(self):
        """Quanto foi acrescentado sobre o custo. Nao confundir com margem."""
        custo = self.variable_cost
        if not custo:
            return Decimal("0.00")
        return (((self.price or 0) - custo) / custo * CEM).quantize(CENTAVO)

    @property
    def is_low_stock(self):
        return self.min_stock > 0 and self.stock <= self.min_stock

    @staticmethod
    def price_for_margin(variable_cost, fee_percent, tax_percent, target_percent):
        """Preco necessario para uma margem alvo.

        margem = preco - custo - preco * taxas  =>  preco = custo / (1 - taxas - alvo)

        Devolve None quando taxas mais alvo chegam a 100%: nesse ponto nenhum
        preco fecha a conta, e mostrar um numero gigante enganaria mais do que
        ajudaria.
        """
        divisor = Decimal("1") - (Decimal(fee_percent) + Decimal(tax_percent) + Decimal(target_percent)) / CEM
        if divisor <= 0:
            return None
        return (Decimal(variable_cost) / divisor).quantize(CENTAVO)


class ProductImage(models.Model):
    """Foto do produto, guardada no proprio banco.

    O disco do Render no plano free e efemero: arquivo salvo la some no proximo
    deploy. Guardar no PostgreSQL sobrevive, nao exige servico externo e da
    conta do tamanho de um catalogo de MEI. A imagem chega ja reduzida pelo
    navegador; o limite abaixo e a rede de protecao do servidor.
    """

    MAX_BYTES = 400 * 1024
    CONTENT_TYPES = ("image/jpeg", "image/png", "image/webp")

    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="image")
    content_type = models.CharField(max_length=40)
    data = models.BinaryField()
    checksum = models.CharField(max_length=64)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Foto de {self.product.name}"
