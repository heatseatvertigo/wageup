from django.db import models
from django.conf import settings


class UserProfile(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Membro"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=24, choices=Role.choices, default=Role.MEMBER)
    business_name = models.CharField(max_length=160, blank=True)
    onboarding_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def can_access_finance(self):
        return self.role == self.Role.ADMIN or self.user.is_staff or self.user.is_superuser

    @property
    def can_manage_payments(self):
        return self.can_access_finance

    def __str__(self):
        return f"{self.user.email or self.user.username} ({self.role})"
