from rest_framework import serializers

from .models import Transaction


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ["id", "description", "type", "amount", "occurred_at", "created_at"]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {"occurred_at": {"required": False}}
