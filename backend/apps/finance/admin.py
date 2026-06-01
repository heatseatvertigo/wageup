from django.contrib import admin

from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["description", "type", "amount", "occurred_at"]
    list_filter = ["type"]
    search_fields = ["description"]

# Register your models here.
