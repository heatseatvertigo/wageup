"""Testes do perfil e das configuracoes da conta (apps/accounts/conta.py).

O que este arquivo trava: cada rota so enxerga o negocio de quem pede; trocar
e-mail, trocar senha e apagar a conta pedem a senha atual; o membro nao recebe
dado do financeiro; nenhuma chave de integracao sai na resposta.
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.businesses.models import Business
from apps.finance.models import Transaction
from apps.payments.models import Payment
from apps.products.models import Product
from apps.sales.models import Sale

from .conta import normalizar_cnpj, normalizar_telefone
from .models import UserProfile

SENHA = "senha-forte-123"
User = get_user_model()


@override_settings(DEEPSEEK_API_KEY="", ANTHROPIC_API_KEY="")
class _ContaBase(TestCase):
    def setUp(self):
        cache.clear()
        self.user, self.negocio, self.client = self._conta("ana@wageup.local", "admin", "Doces da Ana")

    def _conta(self, email, role, negocio):
        user = User.objects.create_user(username=email, email=email, password=SENHA, first_name="Ana")
        UserProfile.objects.create(user=user, role=role, business_name=negocio)
        business = Business.objects.create(owner=user, name=negocio)
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}")
        return user, business, cliente

    def _produto(self, nome, business=None, **campos):
        dados = {"price": Decimal("10"), "cost": Decimal("4"), "stock": 10}
        dados.update(campos)
        return Product.objects.create(business=business or self.negocio, name=nome, **dados)


class PerfilTests(_ContaBase):
    def test_exige_login(self):
        self.assertEqual(APIClient().get("/api/auth/profile/").status_code, 401)

    def test_numeros_do_mes_vem_das_vendas(self):
        bolo = self._produto("Bolo de pote", min_stock=5, stock=3)
        self.client.post("/api/sales/", {"product_id": str(bolo.id), "quantity": 2}, format="json")
        dados = self.client.get("/api/auth/profile/").json()

        self.assertEqual(dados["business"]["name"], "Doces da Ana")
        self.assertEqual(dados["stats"]["sales_count"], 1)
        self.assertEqual(dados["stats"]["units"], 2)
        self.assertEqual(dados["stats"]["revenue"], "20.00")
        self.assertEqual(dados["stats"]["low_stock"], 1)  # 1 no estoque, minimo 5
        self.assertEqual(dados["products"][0]["name"], "Bolo de pote")
        self.assertEqual(dados["products"][0]["sold_month"], 2)

    def test_so_lista_produtos_do_proprio_negocio(self):
        _, outro, _ = self._conta("bia@wageup.local", "admin", "Salão da Bia")
        self._produto("Corte", business=outro)
        self._produto("Brigadeiro")
        nomes = [p["name"] for p in self.client.get("/api/auth/profile/").json()["products"]]
        self.assertEqual(nomes, ["Brigadeiro"])

    def test_membro_nao_recebe_financeiro(self):
        _, _, membro = self._conta("leo@wageup.local", "member", "Marmitas do Léo")
        dados = membro.get("/api/auth/profile/").json()
        self.assertIsNone(dados["goal"])
        self.assertIsNone(dados["pix_pending"])
        self.assertEqual(dados["user"]["role_label"], "Membro")

    def test_admin_ve_pix_pendente(self):
        Payment.objects.create(business=self.negocio, amount=Decimal("45"), status=Payment.Status.PENDING)
        dados = self.client.get("/api/auth/profile/").json()
        self.assertEqual(dados["pix_pending"], {"count": 1, "amount": "45.00"})


class NegocioTests(_ContaBase):
    def test_atualiza_perfil_e_sincroniza_nome(self):
        r = self.client.patch("/api/auth/business/", {
            "name": "Doces da Ana Paula", "cnpj": "11222333000181", "phone": "11912345678",
            "segment": "Alimentação", "city": "São Paulo",
        }, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["cnpj"], "11.222.333/0001-81")
        self.assertEqual(r.json()["phone"], "(11) 91234-5678")
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.business_name, "Doces da Ana Paula")

    def test_recusa_cnpj_com_digito_errado(self):
        r = self.client.patch("/api/auth/business/", {"cnpj": "11.222.333/0001-82"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("cnpj", r.json())

    def test_padroes_podem_ir_para_os_produtos(self):
        bolo = self._produto("Bolo", fee_percent=Decimal("0"), tax_percent=Decimal("0"))
        r = self.client.patch("/api/auth/business/", {
            "default_fee_percent": "4.5", "default_tax_percent": "6", "apply_to_products": True,
        }, format="json")
        self.assertEqual(r.json()["products_updated"], 1)
        bolo.refresh_from_db()
        self.assertEqual(bolo.fee_percent, Decimal("4.50"))
        self.assertEqual(bolo.tax_percent, Decimal("6.00"))
        # O /me leva o padrao, para o cadastro de produto ja vir preenchido.
        self.assertEqual(self.client.get("/api/auth/me/").json()["default_fee_percent"], "4.50")

    def test_padroes_sem_aplicar_nao_mexem_nos_produtos(self):
        bolo = self._produto("Bolo", fee_percent=Decimal("2"))
        self.client.patch("/api/auth/business/", {"default_fee_percent": "4.5"}, format="json")
        bolo.refresh_from_db()
        self.assertEqual(bolo.fee_percent, Decimal("2.00"))

    def test_taxa_e_imposto_somados_abaixo_de_100(self):
        r = self.client.patch("/api/auth/business/", {
            "default_fee_percent": "60", "default_tax_percent": "40",
        }, format="json")
        self.assertEqual(r.status_code, 400)


class ContaTests(_ContaBase):
    def test_troca_nome(self):
        r = self.client.patch("/api/auth/account/", {"name": "Ana Souza"}, format="json")
        self.assertEqual(r.json()["name"], "Ana Souza")

    def test_troca_de_email_pede_senha(self):
        r = self.client.patch("/api/auth/account/", {"email": "nova@wageup.local"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("current_password", r.json())

    def test_email_novo_vira_o_login(self):
        r = self.client.patch("/api/auth/account/", {
            "email": "nova@wageup.local", "current_password": SENHA,
        }, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        login = APIClient().post("/api/auth/login/", {"email": "nova@wageup.local", "password": SENHA}, format="json")
        self.assertEqual(login.status_code, 200)

    def test_email_de_outra_conta_e_recusado(self):
        self._conta("bia@wageup.local", "member", "Salão da Bia")
        r = self.client.patch("/api/auth/account/", {
            "email": "bia@wageup.local", "current_password": SENHA,
        }, format="json")
        self.assertEqual(r.status_code, 400)


class SenhaTests(_ContaBase):
    def test_senha_atual_errada(self):
        r = self.client.post("/api/auth/password/", {
            "current_password": "errada", "new_password": "outra-senha-456",
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_troca_e_derruba_o_token_antigo(self):
        antigo = Token.objects.get(user=self.user).key
        r = self.client.post("/api/auth/password/", {
            "current_password": SENHA, "new_password": "outra-senha-456",
        }, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotEqual(r.json()["token"], antigo)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("outra-senha-456"))

    def test_senha_fraca_e_recusada(self):
        r = self.client.post("/api/auth/password/", {
            "current_password": SENHA, "new_password": "12345678",
        }, format="json")
        self.assertEqual(r.status_code, 400)


class ExclusaoTests(_ContaBase):
    def test_pede_senha_e_confirmacao(self):
        r = self.client.delete("/api/auth/account/", {"password": SENHA, "confirm": "sim"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.delete("/api/auth/account/", {"password": "errada", "confirm": "EXCLUIR"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_apaga_conta_e_negocio(self):
        self._produto("Bolo")
        _, outro, _ = self._conta("bia@wageup.local", "admin", "Salão da Bia")
        self._produto("Corte", business=outro)
        r = self.client.delete("/api/auth/account/", {"password": SENHA, "confirm": "excluir"}, format="json")
        self.assertEqual(r.status_code, 204)
        self.assertFalse(User.objects.filter(email="ana@wageup.local").exists())
        self.assertFalse(Business.objects.filter(name="Doces da Ana").exists())
        # A outra conta continua intacta.
        self.assertEqual(list(Product.objects.values_list("name", flat=True)), ["Corte"])


@override_settings(ABACATE_PAY_API_KEY="chave-secreta-abacate", CLOUDFLARE_ACCOUNT_ID="", CLOUDFLARE_API_TOKEN="")
class ConexoesTests(_ContaBase):
    def test_nao_expoe_chaves(self):
        r = self.client.get("/api/auth/connections/")
        self.assertNotIn("chave-secreta-abacate", r.content.decode())
        pix = next(i for i in r.json()["items"] if i["key"] == "pix")
        self.assertEqual(pix["status"], "active")

    def test_membro_nao_ve_pix_nem_extrato(self):
        _, _, membro = self._conta("leo@wageup.local", "member", "Marmitas do Léo")
        chaves = {i["key"] for i in membro.get("/api/auth/connections/").json()["items"]}
        self.assertNotIn("pix", chaves)
        self.assertNotIn("statement", chaves)


class ExportacaoTests(_ContaBase):
    def _exportar(self, cliente):
        r = cliente.get("/api/auth/export/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r["Content-Disposition"])
        return json.loads(r.content)

    def test_traz_so_os_dados_da_conta(self):
        self._produto("Bolo")
        Transaction.objects.create(business=self.negocio, description="Ingredientes", type="expense", amount=Decimal("30"))
        _, outro, _ = self._conta("bia@wageup.local", "admin", "Salão da Bia")
        self._produto("Corte", business=outro)

        dados = self._exportar(self.client)
        self.assertEqual([p["name"] for p in dados["products"]], ["Bolo"])
        self.assertEqual(len(dados["transactions"]), 1)
        self.assertEqual(dados["account"]["email"], "ana@wageup.local")

    def test_membro_nao_exporta_financeiro(self):
        _, _, membro = self._conta("leo@wageup.local", "member", "Marmitas do Léo")
        dados = self._exportar(membro)
        self.assertNotIn("transactions", dados)
        self.assertNotIn("pix_charges", dados)


class ValidacaoTests(TestCase):
    def test_cnpj_numerico_e_alfanumerico(self):
        self.assertEqual(normalizar_cnpj("11222333000181"), "11.222.333/0001-81")
        # Exemplo de CNPJ alfanumerico divulgado pela Receita Federal.
        self.assertEqual(normalizar_cnpj("12abc34501de35"), "12.ABC.345/01DE-35")
        self.assertEqual(normalizar_cnpj(""), "")
        for invalido in ("11.222.333/0001-82", "1122233300018", "00000000000000"):
            with self.assertRaises(ValueError):
                normalizar_cnpj(invalido)

    def test_telefone(self):
        self.assertEqual(normalizar_telefone("+55 11 91234-5678"), "(11) 91234-5678")
        self.assertEqual(normalizar_telefone("1133334444"), "(11) 3333-4444")
        with self.assertRaises(ValueError):
            normalizar_telefone("1234")


class SenhaGuardadaTests(TestCase):
    """Senha nova sai em Argon2; a antiga em PBKDF2 continua entrando e é
    regravada em Argon2 no primeiro login."""

    def setUp(self):
        cache.clear()

    def test_cadastro_grava_em_argon2(self):
        r = APIClient().post("/api/auth/register/", {
            "name": "Ana", "email": "nova@wageup.local", "password": SENHA, "business_name": "Doces",
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(User.objects.get(email="nova@wageup.local").password.startswith("argon2$"))

    def test_senha_antiga_em_pbkdf2_entra_e_e_atualizada(self):
        from django.contrib.auth.hashers import make_password

        user = User.objects.create(
            username="antiga@wageup.local", email="antiga@wageup.local",
            password=make_password(SENHA, hasher="pbkdf2_sha256"),
        )
        UserProfile.objects.create(user=user, role="member")
        Business.objects.create(owner=user, name="Antigo")
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))

        r = APIClient().post("/api/auth/login/", {"email": "antiga@wageup.local", "password": SENHA}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        user.refresh_from_db()
        self.assertTrue(user.password.startswith("argon2$"))

    def test_parametros_da_owasp(self):
        from .hashers import Argon2OWASPPasswordHasher

        guardada = Argon2OWASPPasswordHasher().encode(SENHA, "saltsaltsaltsalt")
        self.assertIn("m=19456,t=2,p=1", guardada)
