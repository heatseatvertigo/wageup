from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "price", "cost", "stock", "created_at"]
    search_fields = ["name", "category"]

# Register your models here.
