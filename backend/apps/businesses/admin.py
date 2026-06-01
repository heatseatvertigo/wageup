from django.contrib import admin

from .models import Business


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "document", "created_at"]
    search_fields = ["name", "document", "owner__username", "owner__email"]

# Register your models here.
