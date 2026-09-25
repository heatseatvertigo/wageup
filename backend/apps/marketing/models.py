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


class CampaignImage(models.Model):
    """Imagem da campanha, guardada no banco.

    Mesma decisao da foto de produto (products.ProductImage): o disco do
    Render no plano free e efemero, e a imagem precisa continuar existindo
    quando o usuario reabrir uma campanha antiga. Tabela a parte para a
    listagem de campanhas nao arrastar os bytes junto.
    """

    # Maior que o teto da foto de produto: a foto chega reduzida pelo
    # navegador, esta sai do modelo. Ver images.MAX_BYTES.
    MAX_BYTES = 1024 * 1024

    campaign = models.OneToOneField(
        MarketingCampaign, on_delete=models.CASCADE, related_name="image"
    )
    content_type = models.CharField(max_length=40)
    data = models.BinaryField()
    checksum = models.CharField(max_length=64)
    # De qual provedor veio. Util para saber se a imagem tem marca d'agua
    # (Pollinations) ou nao (Cloudflare).
    provider = models.CharField(max_length=40, blank=True)
    prompt = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Imagem da campanha {self.campaign_id}"
