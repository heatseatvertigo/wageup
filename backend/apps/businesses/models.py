from django.db import models
from django.conf import settings


class Business(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="businesses")
    name = models.CharField(max_length=160)
    # Uso interno: o seed_demo grava aqui o marcador da conta de demonstracao.
    # O CNPJ que o MEI digita nas configuracoes fica em `cnpj`.
    document = models.CharField(max_length=32, blank=True)

    # Perfil do negocio, editado nas configuracoes.
    cnpj = models.CharField(max_length=18, blank=True, default="")
    segment = models.CharField(max_length=60, blank=True, default="")
    city = models.CharField(max_length=120, blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")

    # Taxa da maquininha e imposto que o produto novo ja recebe preenchidos.
    # Cada produto continua com os proprios percentuais: o padrao so poupa
    # digitar o mesmo numero em todo cadastro.
    default_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    default_tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
