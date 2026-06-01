from django.contrib import admin

from .models import Payment, PaymentEvent


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["id", "provider", "provider_payment_id", "amount", "status", "created_at"]
    list_filter = ["provider", "status"]
    search_fields = ["provider_payment_id"]


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = ["event_id", "event_type", "provider", "processed_at", "created_at"]
    search_fields = ["event_id", "event_type"]

# Register your models here.
