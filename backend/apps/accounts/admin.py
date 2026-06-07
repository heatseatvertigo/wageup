from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import UserProfile

User = get_user_model()


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    extra = 0
    fields = ["role", "business_name", "onboarding_completed"]


class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = ["email", "first_name", "get_role", "get_business", "is_staff", "date_joined"]
    list_filter = ["is_staff", "is_active", "profile__role"]
    search_fields = ["email", "first_name", "profile__business_name"]
    ordering = ["-date_joined"]

    @admin.display(description="Papel")
    def get_role(self, obj):
        return getattr(obj, "profile", None) and obj.profile.role or "-"

    @admin.display(description="Negócio")
    def get_business(self, obj):
        return getattr(obj, "profile", None) and obj.profile.business_name or "-"


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "business_name", "onboarding_completed", "created_at"]
    list_filter = ["role", "onboarding_completed"]
    search_fields = ["user__email", "user__first_name", "business_name"]
    ordering = ["-created_at"]


admin.site.site_header = "Wage Up — Admin"
admin.site.site_title = "Wage Up"
admin.site.index_title = "Painel de controle"
