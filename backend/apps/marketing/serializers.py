from rest_framework import serializers

from .models import MarketingCampaign


class MarketingCampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketingCampaign
        fields = [
            "id",
            "product",
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
