from rest_framework import serializers

from .models import MarketingCampaign


class MarketingCampaignSerializer(serializers.ModelSerializer):
    # Para a galeria da tela: o nome do produto e se ha imagem, sem a tela
    # precisar buscar cada um.
    product_name = serializers.CharField(source="product.name", read_only=True, default=None)
    has_image = serializers.SerializerMethodField()

    def get_has_image(self, obj):
        return hasattr(obj, "image")

    class Meta:
        model = MarketingCampaign
        fields = [
            "id",
            "product",
            "product_name",
            "has_image",
            "prompt",
            "channel",
            "goal",
            "status",
            "generated_text",
            "image_url",
            "provider",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "generated_text", "image_url", "provider", "metadata", "created_at", "updated_at"]
