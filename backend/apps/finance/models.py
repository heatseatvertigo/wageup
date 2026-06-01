from django.db import models
import uuid


class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        INCOME = "income", "Entrada"
        EXPENSE = "expense", "Saida"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="transactions",
        null=True,
        blank=True,
    )
    description = models.CharField(max_length=180)
    type = models.CharField(max_length=16, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    occurred_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]

    def __str__(self):
        return f"{self.description} - {self.amount}"

# Create your models here.
