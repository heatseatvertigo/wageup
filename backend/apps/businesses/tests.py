"""Testes do comando seed_demo, que monta a conta da apresentacao do TCC."""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.finance.goals import progresso_da_meta
from apps.marketing.recommendations import situacao_dos_produtos
from apps.payments.models import Payment
from apps.sales.models import Sale

from .models import Business

EMAIL = "demo@wageup.local"


@override_settings(ANTHROPIC_API_KEY="", DEEPSEEK_API_KEY="")
class SeedDemoTests(TestCase):
    def _rodar(self, *args):
        saida = StringIO()
        call_command("seed_demo", *args, stdout=saida)
        return saida.getvalue()

    def test_cria_conta_admin_com_um_produto_em_cada_situacao(self):
        saida = self._rodar("--password", "senha-de-teste-123")

        user = get_user_model().objects.get(email=EMAIL)
        self.assertTrue(user.check_password("senha-de-teste-123"))
        self.assertNotIn("Senha gerada", saida)
        self.assertEqual(user.profile.role, UserProfile.Role.ADMIN)
        self.assertTrue(user.profile.onboarding_completed)

        business = Business.objects.get(owner=user)
        situacoes = {linha["name"]: linha["status"] for linha in situacao_dos_produtos(business)}
        self.assertEqual(situacoes["Fatia de bolo de cenoura"], "Prejuízo")
        self.assertEqual(situacoes["Torta de limão"], "Estoque baixo")
        self.assertEqual(situacoes["Bolo de pote"], "Vendas caindo")
        self.assertTrue(situacoes["Cookie recheado"].startswith("Parado"))
        acoes = {linha["name"]: linha["action"] for linha in situacao_dos_produtos(business)}
        self.assertEqual(acoes["Cookie recheado"], "campaign")
        self.assertEqual(acoes["Bolo de pote"], "campaign")
        self.assertEqual(situacoes["Bolo de aniversário (encomenda)"], "Nunca divulgado")
        self.assertEqual(situacoes["Brigadeiro gourmet"], "Em alta")

        hoje = timezone.localdate()
        self.assertIsNotNone(progresso_da_meta(business, hoje.year, hoje.month))
        # PIX pago vira venda pela conciliacao; o pendente vira recebivel.
        self.assertTrue(Sale.objects.filter(business=business, payment__isnull=False).exists())
        self.assertTrue(Payment.objects.filter(business=business, status=Payment.Status.PENDING).exists())

    def test_sem_senha_gera_e_imprime_uma(self):
        saida = self._rodar()

        self.assertIn("Senha gerada:", saida)

    def test_rodar_de_novo_sem_reset_recusa(self):
        self._rodar()

        with self.assertRaises(CommandError):
            self._rodar()

    def test_reset_recria_a_demonstracao(self):
        self._rodar()
        antigo = Business.objects.get(owner__email=EMAIL).pk

        self._rodar("--reset")

        self.assertEqual(Business.objects.filter(owner__email=EMAIL).count(), 1)
        self.assertNotEqual(Business.objects.get(owner__email=EMAIL).pk, antigo)

    def test_reset_nunca_apaga_conta_que_nao_e_de_demonstracao(self):
        User = get_user_model()
        real = User.objects.create_user(username="mei@real.com", email="mei@real.com", password="x")
        Business.objects.create(owner=real, name="Negócio de verdade")

        with self.assertRaises(CommandError):
            self._rodar("--email", "mei@real.com", "--reset")

        self.assertTrue(User.objects.filter(pk=real.pk).exists())
