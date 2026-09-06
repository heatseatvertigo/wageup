from django.db import models
from django.utils import timezone
import uuid


class StatementImport(models.Model):
    """Registro de uma importacao de extrato.

    Guarda so metadado. O arquivo nunca e gravado: ele e lido em memoria e
    descartado, porque extrato bancario e dado sensivel e a funcionalidade nao
    precisa dele depois que os lancamentos existem. O hash fica para avisar o
    usuario quando ele reenvia o mesmo arquivo.
    """

    class Format(models.TextChoices):
        OFX = "ofx", "OFX"
        CSV = "csv", "CSV"
        PDF = "pdf", "PDF"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="statement_imports",
    )
    filename = models.CharField(max_length=200)
    file_format = models.CharField(max_length=8, choices=Format.choices)
    file_hash = models.CharField(max_length=64, db_index=True)
    imported_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.filename} ({self.imported_count} lancamentos)"


class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        INCOME = "income", "Entrada"
        EXPENSE = "expense", "Saida"

    class Source(models.TextChoices):
        MANUAL = "manual", "Lancamento manual"
        PIX = "pix", "Cobranca PIX"
        IMPORT = "import", "Extrato importado"

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
    # De onde veio o lancamento. Sem isto, uma entrada conciliada do PIX fica
    # indistinguivel de uma digitada a mao, e o usuario nao sabe o que pode
    # editar com seguranca.
    source = models.CharField(
        max_length=16,
        choices=Source.choices,
        default=Source.MANUAL,
    )
    # Data do lançamento. Por padrão captura o momento da criação, mas é
    # editável para permitir lançar movimentações retroativas (ex.: um
    # pagamento recebido em outro dia).
    occurred_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    # Identificador do lancamento no extrato de origem: o FITID quando o banco
    # fornece, ou uma impressao digital do conteudo quando nao. E o que sustenta
    # a restricao de unicidade abaixo — sem ele, reimportar o mesmo extrato
    # duplicaria tudo e o financeiro passaria a mentir.
    external_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    statement_import = models.ForeignKey(
        "finance.StatementImport",
        on_delete=models.SET_NULL,
        related_name="transactions",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-occurred_at"]
        constraints = [
            # Lancamento manual nao tem external_id, e varios deles convivem com
            # o campo vazio. A condicao exclui o vazio da regra.
            models.UniqueConstraint(
                fields=["business", "external_id"],
                condition=~models.Q(external_id=""),
                name="transaction_external_id_unico_por_business",
            ),
        ]

    def __str__(self):
        return f"{self.description} - {self.amount}"

# Create your models here.


class AssistantConversation(models.Model):
    """Uma conversa com o assistente financeiro.

    Antes o histórico vivia só na memória do navegador e sumia ao recarregar.
    Persistir aqui também deixa o servidor dono da conversa: o cliente manda
    apenas a nova pergunta, sem poder forjar o que foi dito antes.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="assistant_conversations",
    )
    title = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title or f"Conversa {self.id}"


class AssistantMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "Usuario"
        ASSISTANT = "assistant", "Assistente"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        AssistantConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
