from rest_framework import serializers

from .models import Transaction


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ["id", "description", "type", "amount", "occurred_at", "created_at"]
        read_only_fields = ["id", "occurred_at", "created_at"]
