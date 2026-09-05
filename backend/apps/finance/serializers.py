from decimal import Decimal

from rest_framework import serializers

from .models import StatementImport, Transaction


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ["id", "description", "type", "amount", "source", "occurred_at", "created_at"]
        read_only_fields = ["id", "source", "created_at"]
        extra_kwargs = {"occurred_at": {"required": False}}


class StatementRowSerializer(serializers.Serializer):
    """Uma linha do extrato depois da conferencia do usuario.

    O cliente pode ter mudado descricao e tipo antes de confirmar, entao o
    servidor valida tudo de novo. Isso nao e brecha: criar lancamento a mao ja
    e permitido, ninguem ganha permissao nova por este caminho.
    """

    external_id = serializers.CharField(max_length=120, allow_blank=True, required=False, default="")
    occurred_at = serializers.DateTimeField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    type = serializers.ChoiceField(choices=Transaction.TransactionType.choices)
    description = serializers.CharField(max_length=180)


class StatementConfirmSerializer(serializers.Serializer):
    filename = serializers.CharField(max_length=200)
    file_format = serializers.ChoiceField(choices=StatementImport.Format.choices)
    file_hash = serializers.CharField(max_length=64)
    transactions = StatementRowSerializer(many=True, allow_empty=False)
