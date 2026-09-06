from django.contrib import admin

from .models import Product, ProductImage


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "price", "cost", "margem", "stock", "is_active", "owner_email", "created_at"]
    list_filter = ["category", "unit", "is_active"]
    search_fields = ["name", "sku", "category", "business__owner__email"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at", "updated_at"]

    @admin.display(description="Margem", ordering="price")
    def margem(self, obj):
        # A margem real, com taxas e outros custos — nao a diferenca simples
        # entre preco e custo, que engana.
        return f"R$ {obj.margin_value:.2f} ({obj.margin_percent:.0f}%)"

    @admin.display(description="Dono")
    def owner_email(self, obj):
        return obj.business.owner.email if obj.business else "-"


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ["product", "content_type", "tamanho", "updated_at"]
    list_filter = ["content_type"]
    search_fields = ["product__name"]
    readonly_fields = ["checksum", "updated_at"]
    # O campo binario nao tem por que aparecer no formulario do admin.
    exclude = ["data"]

    @admin.display(description="Tamanho")
    def tamanho(self, obj):
        return f"{len(obj.data) / 1024:.0f} KB"
