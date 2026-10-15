from django.contrib import admin

from .models import Goal, StatementImport, Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["description", "type", "amount", "source", "owner_email", "occurred_at"]
    list_filter = ["type", "source"]
    search_fields = ["description", "business__owner__email"]
    ordering = ["-occurred_at"]
    readonly_fields = ["id", "occurred_at", "created_at"]

    @admin.display(description="Dono")
    def owner_email(self, obj):
        return obj.business.owner.email if obj.business else "-"


@admin.register(StatementImport)
class StatementImportAdmin(admin.ModelAdmin):
    list_display = ["filename", "file_format", "imported_count", "skipped_count", "owner_email", "created_at"]
    list_filter = ["file_format"]
    search_fields = ["filename", "file_hash", "business__owner__email"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "file_hash", "created_at"]

    @admin.display(description="Dono")
    def owner_email(self, obj):
        return obj.business.owner.email if obj.business else "-"


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ["month", "target_amount", "owner_email", "updated_at"]
    search_fields = ["business__owner__email"]
    ordering = ["-month"]

    @admin.display(description="Dono")
    def owner_email(self, obj):
        return obj.business.owner.email
