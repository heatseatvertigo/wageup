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


class PaymentEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentEvent
        fields = ["id", "provider", "event_id", "event_type", "raw_payload", "processed_at", "created_at"]
        read_only_fields = ["id", "processed_at", "created_at"]
