from django.db import models
import uuid


class MarketingCampaign(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Na fila"
        PROCESSING = "processing", "Processando"
        COMPLETED = "completed", "Concluida"
        FAILED = "failed", "Falhou"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="marketing_campaigns",
        null=True,
        blank=True,
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.SET_NULL,
        related_name="marketing_campaigns",
        null=True,
        blank=True,
    )
    prompt = models.TextField()
    channel = models.CharField(max_length=80)
    goal = models.CharField(max_length=80)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.QUEUED)
    generated_text = models.TextField(blank=True)
    image_url = models.URLField(blank=True)
    provider = models.CharField(max_length=80, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

# Create your models here.
