from decimal import Decimal

from rest_framework import serializers

from .models import Sale


class SaleSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField(source="product.id", read_only=True, allow_null=True)
    source = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = [
            "id", "product_id", "product_name", "quantity",
            "unit_price", "unit_cost", "fee_percent", "tax_percent",
            "total", "cost_total", "fees", "profit",
            "payment_method", "status", "source", "occurred_at", "canceled_at", "created_at",
        ]
        read_only_fields = fields

    def get_source(self, obj):
        # A tela so oferece cancelar a venda registrada nela: a venda de PIX
        # se desfaz pelo estorno da cobranca.
        return "pix" if obj.payment_id else "manual"


class SaleCreateSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(
        min_value=1, max_value=100000,
        error_messages={"min_value": "Informe uma quantidade maior que zero."},
    )
    # Opcional: sem ele, vale o preco do cadastro. Com ele, registra desconto
    # ou preco combinado. Custos e taxas vem sempre do banco.
    unit_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False,
        error_messages={"min_value": "O preço não pode ser negativo."},
    )
    payment_method = serializers.ChoiceField(choices=Sale.PaymentMethod.choices, default=Sale.PaymentMethod.CASH)
    occurred_at = serializers.DateTimeField(required=False)
