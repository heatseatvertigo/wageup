"""Testes do cadastro de produtos.

O foco e o calculo de margem e a foto. Margem errada faz o MEI precificar no
prejuizo achando que esta lucrando — e o tipo de erro que nao aparece na tela,
so no fim do mes.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import UserProfile
from apps.businesses.models import Business

from .models import Product, ProductImage

# PNG valido de 1x1, o menor arquivo que passa pela validacao de tipo.
PNG_MINIMO = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000100ffff03000006000557bfabd400"
    "00000049454e44ae426082"
)


class MargemTests(TestCase):
    def _produto(self, **campos):
        padrao = {"name": "Bolo", "price": Decimal("50.00"), "cost": Decimal("20.00")}
        return Product(**{**padrao, **campos})

    def test_margem_simples_e_preco_menos_custo(self):
        produto = self._produto()
        self.assertEqual(produto.margin_value, Decimal("30.00"))
        self.assertEqual(produto.margin_percent, Decimal("60.00"))

    def test_outros_custos_entram_na_margem(self):
        # Embalagem e o custo que some da conta quando so existe "custo".
        produto = self._produto(other_costs=Decimal("5.00"))
        self.assertEqual(produto.variable_cost, Decimal("25.00"))
        self.assertEqual(produto.margin_value, Decimal("25.00"))

    def test_taxa_e_imposto_incidem_sobre_o_preco(self):
        produto = self._produto(fee_percent=Decimal("4.00"), tax_percent=Decimal("6.00"))
        # 10% de 50 = 5,00 em taxas.
        self.assertEqual(produto.fee_amount, Decimal("5.00"))
        self.assertEqual(produto.margin_value, Decimal("25.00"))
        self.assertEqual(produto.margin_percent, Decimal("50.00"))

    def test_markup_nao_e_margem(self):
        # Custo 20, preco 50: markup de 150%, margem de 60%. Confundir os dois
        # e o erro classico de precificacao.
        produto = self._produto()
        self.assertEqual(produto.markup_percent, Decimal("150.00"))
        self.assertEqual(produto.margin_percent, Decimal("60.00"))

    def test_preco_zero_nao_divide_por_zero(self):
        produto = self._produto(price=Decimal("0"))
        self.assertEqual(produto.margin_percent, Decimal("0.00"))

    def test_custo_zero_nao_divide_por_zero(self):
        produto = self._produto(cost=Decimal("0"), other_costs=Decimal("0"))
        self.assertEqual(produto.markup_percent, Decimal("0.00"))

    def test_preco_sugerido_devolve_a_margem_pedida(self):
        preco = Product.price_for_margin(Decimal("25.00"), Decimal("4"), Decimal("6"), Decimal("30"))
        conferencia = Product(name="x", price=preco, cost=Decimal("25.00"),
                              fee_percent=Decimal("4"), tax_percent=Decimal("6"))
        # A margem calculada de volta bate com o alvo, a menos do arredondamento.
        self.assertAlmostEqual(float(conferencia.margin_percent), 30.0, places=1)

    def test_margem_alvo_impossivel_devolve_nada(self):
        # 70% de taxas mais 40% de margem nao cabem em 100% do preco.
        self.assertIsNone(
            Product.price_for_margin(Decimal("10"), Decimal("40"), Decimal("30"), Decimal("40"))
        )

    def test_estoque_baixo_so_alerta_com_minimo_definido(self):
        self.assertFalse(self._produto(stock=0, min_stock=0).is_low_stock)
        self.assertTrue(self._produto(stock=2, min_stock=5).is_low_stock)
        self.assertFalse(self._produto(stock=9, min_stock=5).is_low_stock)


class ProdutoEndpointTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="dono@wageup.local", email="dono@wageup.local", password="x")
        UserProfile.objects.create(user=self.user, role="member")
        self.business = Business.objects.create(owner=self.user, name="Negocio")
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.user).key}")

    def _criar(self, **campos):
        corpo = {"name": "Bolo", "price": "50.00", "cost": "20.00", **campos}
        return self.client.post("/api/products/", corpo, format="json")

    def test_cria_produto_e_devolve_a_margem_calculada(self):
        resposta = self._criar(other_costs="5.00", fee_percent="4.00")

        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(resposta.data["variable_cost"], "25.00")
        self.assertEqual(resposta.data["margin_value"], "23.00")
        self.assertFalse(resposta.data["has_image"])

    def test_percentual_fora_da_faixa_e_recusado(self):
        self.assertEqual(self._criar(fee_percent="120").status_code, 400)
        self.assertEqual(self._criar(tax_percent="-1").status_code, 400)

    def test_valor_negativo_e_recusado(self):
        self.assertEqual(self._criar(price="-1").status_code, 400)

    def test_envia_le_e_remove_a_foto(self):
        produto_id = self._criar().data["id"]
        arquivo = SimpleUploadedFile("foto.png", PNG_MINIMO, content_type="image/png")

        envio = self.client.post(f"/api/products/{produto_id}/image/", {"file": arquivo})
        self.assertEqual(envio.status_code, 201)
        self.assertTrue(envio.data["has_image"])

        leitura = self.client.get(f"/api/products/{produto_id}/image/")
        self.assertEqual(leitura.status_code, 200)
        self.assertEqual(leitura["Content-Type"], "image/png")
        self.assertEqual(leitura.content, PNG_MINIMO)

        # O ETag evita rebaixar a mesma foto a cada visita.
        recarga = self.client.get(
            f"/api/products/{produto_id}/image/", HTTP_IF_NONE_MATCH=leitura["ETag"]
        )
        self.assertEqual(recarga.status_code, 304)

        self.assertEqual(self.client.delete(f"/api/products/{produto_id}/image/").status_code, 204)
        self.assertEqual(self.client.get(f"/api/products/{produto_id}/image/").status_code, 404)

    def test_formato_de_arquivo_nao_aceito(self):
        produto_id = self._criar().data["id"]
        arquivo = SimpleUploadedFile("planilha.csv", b"a,b", content_type="text/csv")

        resposta = self.client.post(f"/api/products/{produto_id}/image/", {"file": arquivo})
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(ProductImage.objects.exists())

    def test_foto_grande_demais_e_recusada(self):
        produto_id = self._criar().data["id"]
        gigante = SimpleUploadedFile("foto.png", b"\x00" * (ProductImage.MAX_BYTES + 1), content_type="image/png")

        resposta = self.client.post(f"/api/products/{produto_id}/image/", {"file": gigante})
        self.assertEqual(resposta.status_code, 413)
        self.assertFalse(ProductImage.objects.exists())

    def test_produto_de_outro_negocio_fica_invisivel(self):
        produto_id = self._criar().data["id"]

        User = get_user_model()
        outro = User.objects.create_user(username="o@wageup.local", email="o@wageup.local", password="x")
        UserProfile.objects.create(user=outro, role="member")
        Business.objects.create(owner=outro, name="Outro")
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=outro).key}")

        self.assertEqual(cliente.get("/api/products/").data, [])
        self.assertEqual(cliente.get(f"/api/products/{produto_id}/").status_code, 404)
        self.assertEqual(cliente.get(f"/api/products/{produto_id}/image/").status_code, 404)
