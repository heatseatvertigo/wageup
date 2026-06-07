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
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    description = serializers.CharField(max_length=180, required=False, allow_blank=True)
    customer_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    customer_email = serializers.EmailField(required=False, allow_blank=True)
    customer_tax_id = serializers.CharField(max_length=32, required=False, allow_blank=True)
    customer_cellphone = serializers.CharField(max_length=32, required=False, allow_blank=True)

    def get_amount_cents(self):
        return int(self.validated_data["amount"] * 100)


class PaymentEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentEvent
        fields = ["id", "provider", "event_id", "event_type", "raw_payload", "processed_at", "created_at"]
        read_only_fields = ["id", "processed_at", "created_at"]
