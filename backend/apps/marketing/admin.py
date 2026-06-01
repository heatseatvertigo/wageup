from django.contrib import admin

from .models import MarketingCampaign


@admin.register(MarketingCampaign)
class MarketingCampaignAdmin(admin.ModelAdmin):
    list_display = ["prompt", "channel", "goal", "status", "provider", "created_at"]
    list_filter = ["status", "channel", "goal"]
    search_fields = ["prompt", "generated_text"]

# Register your models here.
