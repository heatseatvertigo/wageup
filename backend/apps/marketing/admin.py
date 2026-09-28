from django.contrib import admin

from .models import MarketingCampaign, MarketingConversation


@admin.register(MarketingCampaign)
class MarketingCampaignAdmin(admin.ModelAdmin):
    list_display = ["short_prompt", "channel", "goal", "status", "provider", "owner_email", "created_at"]
    list_filter = ["status", "channel", "goal", "provider"]
    search_fields = ["prompt", "generated_text", "business__owner__email"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at", "updated_at"]

    @admin.display(description="Prompt")
    def short_prompt(self, obj):
        return obj.prompt[:60] + "..." if len(obj.prompt) > 60 else obj.prompt

    @admin.display(description="Dono")
    def owner_email(self, obj):
        return obj.business.owner.email if obj.business else "-"


@admin.register(MarketingConversation)
class MarketingConversationAdmin(admin.ModelAdmin):
    list_display = ["title", "business", "updated_at"]
    search_fields = ["title", "business__owner__email"]
    ordering = ["-updated_at"]
    readonly_fields = ["id", "created_at", "updated_at"]
