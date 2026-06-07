from django.contrib import admin

from .models import Payment, PaymentEvent


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["short_id", "amount", "status", "provider", "owner_email", "created_at"]
    list_filter = ["status", "provider"]
    search_fields = ["provider_payment_id", "business__owner__email"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "provider_payment_id", "created_at", "updated_at"]

    @admin.display(description="ID")
    def short_id(self, obj):
        return str(obj.id)[:8] + "..."

    @admin.display(description="Dono")
    def owner_email(self, obj):
        return obj.business.owner.email if obj.business else "-"


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = ["event_id", "event_type", "provider", "processed_at", "created_at"]
    list_filter = ["provider", "event_type"]
    search_fields = ["event_id"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at"]
