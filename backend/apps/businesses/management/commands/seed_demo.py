"""Cria uma conta de demonstracao com dois meses de dados realistas.

Uso:
    python backend/manage.py seed_demo
    python backend/manage.py seed_demo --email demo@wageup.com.br --password "..."
    python backend/manage.py seed_demo --reset

A conta e de uma confeitaria fictícia e cobre o fluxo inteiro do escopo do
TCC: vendas em PIX, dinheiro e cartao, despesas, meta do mes, cobranca PIX
paga e pendente, campanha e um produto em cada situacao do marketing
(vendas caindo, parado, estoque baixo, prejuizo, nunca divulgado, em alta).

As datas sao relativas ao dia em que o comando roda: rodado de novo antes da
apresentacao, a demonstracao continua com "vendas caindo" na ultima semana.

Seguranca: o negocio criado leva o marcador DEMO_MARKER em `document`. O
--reset so apaga uma conta que tenha esse marcador, para o comando nunca
servir de atalho para apagar a conta de alguem.
"""
import random
import secrets
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.businesses.models import Business
from apps.finance.models import Goal, Transaction
from apps.marketing.models import MarketingCampaign
from apps.payments.models import Payment
from apps.payments.views import record_finance_income
from apps.products.models import Product
from apps.sales.models import Sale
from apps.sales.services import registrar_venda

DEMO_MARKER = "DEMO-WAGEUP"
DEFAULT_EMAIL = "demo@wageup.local"
BUSINESS_NAME = "Doces da Ana"
DIAS_DE_HISTORICO = 60

# Estoque de partida alto para as vendas do historico nunca esbarrarem no
# limite; no fim cada produto recebe o estoque "de hoje".
ESTOQUE_INICIAL = 100000

PRODUTOS = {
    "brigadeiro": dict(
        name="Brigadeiro gourmet", category="Doces", price="4.00", cost="1.20", other_costs="0.30",
        fee_percent="3", tax_percent="6", min_stock=40, estoque_final=180,
        description="Brigadeiro de chocolate belga, unidade.",
    ),
    "bolo_pote": dict(
        name="Bolo de pote", category="Bolos", price="15.00", cost="5.00", other_costs="1.00",
        fee_percent="3", tax_percent="6", min_stock=8, estoque_final=25,
        description="Bolo de pote de 250 ml, sabores variados.",
    ),
    "torta": dict(
        name="Torta de limão", category="Tortas", price="70.00", cost="28.00", other_costs="4.00",
        fee_percent="3", tax_percent="6", min_stock=3, estoque_final=2,
        description="Torta inteira, serve 10 fatias.",
    ),
    "cookie": dict(
        name="Cookie recheado", category="Doces", price="8.00", cost="2.50", other_costs="0.50",
        fee_percent="3", tax_percent="6", min_stock=10, estoque_final=35,
        description="Cookie com recheio de Nutella.",
    ),
    "fatia": dict(
        name="Fatia de bolo de cenoura", category="Bolos", price="7.00", cost="6.00", other_costs="1.20",
        fee_percent="4", tax_percent="6", min_stock=5, estoque_final=20,
        description="Fatia com cobertura de chocolate. Preço desatualizado: o custo subiu.",
    ),
    "encomenda": dict(
        name="Bolo de aniversário (encomenda)", category="Encomendas", price="180.00", cost="70.00",
        other_costs="15.00", fee_percent="3", tax_percent="6", unit=Product.Unit.SERVICE,
        min_stock=0, estoque_final=0, description="Bolo decorado de 2 kg, sob encomenda.",
    ),
}


class Command(BaseCommand):
    help = "Cria uma conta de demonstração com dois meses de vendas, despesas, meta, PIX e campanha."

    def add_arguments(self, parser):
        parser.add_argument("--email", default=DEFAULT_EMAIL)
        parser.add_argument("--password", help="Senha da conta. Sem ela, uma senha aleatória é gerada e impressa.")
        parser.add_argument(
            "--reset", action="store_true",
            help="Apaga a conta de demonstração com este e-mail e cria de novo.",
        )

    def handle(self, *args, email, password, reset, **options):
        email = email.strip().lower()
        User = get_user_model()
        existente = User.objects.filter(email__iexact=email).first()
        if existente:
            if not reset:
                raise CommandError(f"Já existe uma conta com {email}. Use --reset para recriar a demonstração.")
            if not Business.objects.filter(owner=existente, document=DEMO_MARKER).exists():
                raise CommandError(
                    f"A conta {email} não foi criada por este comando. O --reset só apaga contas de demonstração."
                )

        senha = password or secrets.token_urlsafe(9)
        with transaction.atomic():
            if existente:
                existente.delete()
            business = self._criar_conta(User, email, senha)
            resumo = self._popular(business)

        self.stdout.write(self.style.SUCCESS(f"Conta de demonstração pronta: {email}"))
        if not password:
            self.stdout.write(f"Senha gerada: {senha}")
        self.stdout.write(
            f"{resumo['vendas']} vendas, {resumo['despesas']} despesas, meta de "
            f"R$ {resumo['meta']:.2f} para este mês."
        )

    def _criar_conta(self, User, email, senha):
        user = User.objects.create_user(username=email, email=email, password=senha, first_name="Ana")
        # Admin para a demonstração mostrar o financeiro, que é o núcleo do
        # escopo. Não passa por WAGEUP_ADMIN_EMAILS: é uma conta fictícia.
        UserProfile.objects.create(
            user=user, role=UserProfile.Role.ADMIN, business_name=BUSINESS_NAME, onboarding_completed=True,
        )
        return Business.objects.create(owner=user, name=BUSINESS_NAME, document=DEMO_MARKER)

    def _popular(self, business):
        rnd = random.Random(7)  # mesma demonstração toda vez
        agora = timezone.localtime()
        hoje = agora.date()
        user = business.owner

        produtos = {}
        for chave, dados in PRODUTOS.items():
            dados = dict(dados)
            dados.pop("estoque_final")
            campos = {k: Decimal(v) if k in ("price", "cost", "other_costs", "fee_percent", "tax_percent") else v
                      for k, v in dados.items()}
            produtos[chave] = Product.objects.create(business=business, stock=ESTOQUE_INICIAL, **campos)
        # Cadastrados ha 75 dias: "parado" so vale para produto com mais de 30.
        Product.objects.filter(business=business).update(created_at=agora - timedelta(days=75))

        def forma():
            sorteio = rnd.random()
            return "pix" if sorteio < 0.5 else "dinheiro" if sorteio < 0.8 else "cartao"

        def vender(chave, quantidade, dias_atras):
            hora = agora.replace(hour=rnd.randint(9, 18), minute=rnd.randint(0, 59), second=0, microsecond=0)
            quando = min(hora - timedelta(days=dias_atras), agora)
            registrar_venda(
                business=business, produto=produtos[chave], quantidade=quantidade,
                payment_method=forma(), occurred_at=quando, user=user,
            )

        for dias in range(DIAS_DE_HISTORICO, -1, -1):
            dia = hoje - timedelta(days=dias)
            if dia.weekday() == 0 and dias > 0:  # segunda: confeitaria fechada
                continue
            vender("brigadeiro", rnd.randint(6, 14) + (3 if dias < 14 else 0), dias)
            # Bolo de pote: vendia bem e caiu na última semana.
            if dias <= 7:
                if dias in (2, 5):
                    vender("bolo_pote", 1, dias)
            elif dias <= 14:
                vender("bolo_pote", rnd.randint(3, 4), dias)
            else:
                vender("bolo_pote", rnd.randint(2, 3), dias)
            if dias % 5 == 0:
                vender("torta", 1, dias)
            # Cookie: parou de vender há mais de 30 dias.
            if dias >= 35 and dias % 2 == 0:
                vender("cookie", rnd.randint(2, 4), dias)
            # Fatia em prejuízo continua vendendo: o MEI não percebeu.
            if dias <= 40 and dias % 2 == 1:
                vender("fatia", rnd.randint(2, 4), dias)
            if dias in (6, 19, 33, 47):
                vender("encomenda", 1, dias)

        despesas = self._despesas(business, hoje, rnd)
        self._pix(business, produtos, agora)

        for chave, dados in PRODUTOS.items():
            Product.objects.filter(pk=produtos[chave].pk).update(stock=dados["estoque_final"])

        MarketingCampaign.objects.create(
            business=business, product=produtos["brigadeiro"], prompt="Promoção de brigadeiro para o fim de semana",
            channel="Instagram", goal="promocao", status=MarketingCampaign.Status.COMPLETED, provider="local-demo",
            generated_text=(
                "**Chamada principal:** Caixa com 12 brigadeiros por R$ 42 neste fim de semana\n\n"
                "**Ideia de imagem:** caixa aberta de brigadeiros gourmet sobre mesa de madeira, luz natural.\n\n"
                "**Legenda:** Chocolate belga, granulado crocante e aquele ponto certinho. "
                "Garanta a sua caixa para o fim de semana.\n\n"
                "**CTA:** Peça pelo direct ou pague pelo PIX."
            ),
        )
        MarketingCampaign.objects.filter(business=business).update(created_at=agora - timedelta(days=20))

        meta = self._metas(business, hoje)
        return {"vendas": Sale.objects.filter(business=business).count(), "despesas": despesas, "meta": meta}

    def _despesas(self, business, hoje, rnd):
        lancamentos = []
        for dias in range(DIAS_DE_HISTORICO, -1, -1):
            dia = hoje - timedelta(days=dias)
            if dia.day == 5:
                lancamentos.append(("Aluguel da cozinha", Decimal("450.00"), dia))
            if dia.day == 12:
                lancamentos.append(("Embalagens e etiquetas", Decimal("135.00"), dia))
            if dia.day == 20:
                lancamentos.append(("Botijão de gás", Decimal("120.00"), dia))
            if dia.weekday() == 1:  # terça: compra no atacado
                lancamentos.append(("Ingredientes (atacado)", Decimal(rnd.randint(240, 330)), dia))
        for descricao, valor, dia in lancamentos:
            Transaction.objects.create(
                business=business, description=descricao, type=Transaction.TransactionType.EXPENSE,
                amount=valor, payment_method=Transaction.PaymentMethod.PIX,
                occurred_at=timezone.make_aware(timezone.datetime(dia.year, dia.month, dia.day, 10)),
            )
        return len(lancamentos)

    def _pix(self, business, produtos, agora):
        # Cobrança de produto já paga: vira venda pela conciliação, como no
        # webhook de verdade.
        pago = Payment.objects.create(
            business=business, amount=Decimal("120.00"), status=Payment.Status.PAID,
            provider_payment_id="demo_pago",
            metadata={
                "description": "30 brigadeiros para festa", "product_id": str(produtos["brigadeiro"].id),
                "quantity": 30, "customer": {"name": "Mariana Costa"},
            },
        )
        record_finance_income(pago)
        pago.save(update_fields=["metadata"])
        quando = agora - timedelta(days=2)
        Payment.objects.filter(pk=pago.pk).update(created_at=quando)
        Transaction.objects.filter(pk=pago.metadata["finance_transaction_id"]).update(occurred_at=quando)
        Sale.objects.filter(payment=pago).update(occurred_at=quando)

        Payment.objects.create(
            business=business, amount=Decimal("180.00"), status=Payment.Status.PENDING,
            provider_payment_id="demo_pendente",
            metadata={"description": "Bolo de aniversário para sábado", "customer": {"name": "Carlos Lima"}},
        )

    def _metas(self, business, hoje):
        from apps.finance.goals import faturamento_do_mes

        inicio_mes = hoje.replace(day=1)
        anterior = (inicio_mes - timedelta(days=1)).replace(day=1)
        feito_anterior = faturamento_do_mes(business, anterior.year, anterior.month)
        # Mês passado: meta batida com folga. Este mês: 15% acima do que
        # entrou no anterior, arredondado para cima de R$ 100 em R$ 100.
        Goal.objects.create(
            business=business, month=anterior,
            target_amount=(feito_anterior * Decimal("0.9") / 100).quantize(Decimal("1")) * 100,
        )
        alvo = (feito_anterior * Decimal("1.15") / 100).to_integral_value(rounding="ROUND_CEILING") * 100
        Goal.objects.create(business=business, month=inicio_mes, target_amount=alvo)
        return alvo
