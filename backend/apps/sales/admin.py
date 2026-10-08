from django.contrib import admin

from .models import Sale


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ["product_name", "quantity", "total", "profit", "payment_method", "status", "owner_email", "occurred_at"]
    list_filter = ["status", "payment_method"]
    search_fields = ["product_name", "business__owner__email"]
    ordering = ["-occurred_at"]
    readonly_fields = [field.name for field in Sale._meta.fields]

    @admin.display(description="Dono")
    def owner_email(self, obj):
        return obj.business.owner.email if obj.business else "-"
