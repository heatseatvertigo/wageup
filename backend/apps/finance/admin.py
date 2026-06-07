from django.contrib import admin

from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["description", "type", "amount", "owner_email", "occurred_at"]
    list_filter = ["type"]
    search_fields = ["description", "business__owner__email"]
    ordering = ["-occurred_at"]
    readonly_fields = ["id", "occurred_at", "created_at"]

    @admin.display(description="Dono")
    def owner_email(self, obj):
        return obj.business.owner.email if obj.business else "-"
