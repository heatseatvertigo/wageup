from rest_framework import serializers

from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    # Calculados no modelo. Vem prontos para a tela nao ter que refazer a conta
    # ao listar — a formula da tela existe so para o retorno ao vivo do form.
    variable_cost = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    fee_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    margin_value = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    margin_percent = serializers.DecimalField(max_digits=7, decimal_places=2, read_only=True)
    markup_percent = serializers.DecimalField(max_digits=9, decimal_places=2, read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    has_image = serializers.SerializerMethodField()
    image_updated_at = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "name", "sku", "category", "description", "unit",
            "price", "cost", "other_costs", "fee_percent", "tax_percent",
            "stock", "min_stock", "is_active",
            "variable_cost", "fee_amount", "margin_value", "margin_percent",
            "markup_percent", "is_low_stock",
            "has_image", "image_updated_at",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_has_image(self, obj):
        return hasattr(obj, "image")

    def get_image_updated_at(self, obj):
        # A tela usa isto para invalidar o cache da foto sem recarregar a
        # pagina: mudou a data, busca de novo.
        return obj.image.updated_at.isoformat() if hasattr(obj, "image") else None

    def validate_fee_percent(self, valor):
        return self._percentual(valor, "taxa")

    def validate_tax_percent(self, valor):
        return self._percentual(valor, "imposto")

    @staticmethod
    def _percentual(valor, nome):
        if valor < 0 or valor > 100:
            raise serializers.ValidationError(f"O percentual de {nome} precisa ficar entre 0 e 100.")
        return valor

    def validate(self, dados):
        for campo in ("price", "cost", "other_costs"):
            if campo in dados and dados[campo] < 0:
                raise serializers.ValidationError({campo: "Valor nao pode ser negativo."})
        return dados
