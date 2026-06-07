from django.contrib import admin

from .models import Business


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ["name", "owner_email", "document", "created_at"]
    search_fields = ["name", "document", "owner__email", "owner__first_name"]
    ordering = ["-created_at"]
    readonly_fields = ["created_at", "updated_at"]

    @admin.display(description="E-mail do dono")
    def owner_email(self, obj):
        return obj.owner.email
