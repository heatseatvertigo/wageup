from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "price", "cost", "margin", "stock", "owner_email", "created_at"]
    list_filter = ["category"]
    search_fields = ["name", "category", "business__owner__email"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at", "updated_at"]

    @admin.display(description="Margem (R$)", ordering="price")
    def margin(self, obj):
        return f"R$ {obj.price - obj.cost:.2f}"

    @admin.display(description="Dono")
    def owner_email(self, obj):
        return obj.business.owner.email if obj.business else "-"
