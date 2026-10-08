from decimal import Decimal

from rest_framework import serializers

from .models import Payment, PaymentEvent


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "provider",
            "provider_payment_id",
            "amount",
            "status",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "provider", "provider_payment_id", "status", "metadata", "created_at", "updated_at"]


class PixChargeCreateSerializer(serializers.Serializer):
    # A tela ja bloqueia valor zero, mas a API nao pode depender dela: sem o
    # minimo, uma chamada direta criava a cobranca e ia ate a Abacate Pay.
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        error_messages={"min_value": "Informe um valor maior que zero."},
    )
    description = serializers.CharField(max_length=180, required=False, allow_blank=True)
    customer_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    customer_email = serializers.EmailField(required=False, allow_blank=True)
    customer_tax_id = serializers.CharField(max_length=32, required=False, allow_blank=True)
    customer_cellphone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    # Cobranca de um produto do catalogo: paga, vira uma venda e baixa o estoque.
    product_id = serializers.UUIDField(required=False, allow_null=True)
    quantity = serializers.IntegerField(
        min_value=1, max_value=100000, required=False, default=1,
        error_messages={"min_value": "Informe uma quantidade maior que zero."},
    )

    def get_amount_cents(self):
        return int(self.validated_data["amount"] * 100)


class PaymentEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentEvent
        fields = ["id", "provider", "event_id", "event_type", "raw_payload", "processed_at", "created_at"]
        read_only_fields = ["id", "processed_at", "created_at"]
