"""Testes da geracao de campanha.

Dois pontos: o caminho de falha (chave invalida ou provedor fora do ar nao
pode deixar o usuario sem campanha nenhuma) e os numeros que vao para a IA,
que saem do produto no banco e nao do corpo da requisicao.
"""
from decimal import Decimal
from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import UserProfile
from apps.businesses.models import Business
from apps.products.models import Product

from .images import extrair_prompt, gerar_imagem
from .models import CampaignImage, MarketingCampaign


# Sem provedor de imagem: estes testes sao do texto da campanha. Fixar aqui
# evita que um .env com chave da Cloudflare faca a suite bater na rede.
SEM_IMAGEM = override_settings(
    CLOUDFLARE_ACCOUNT_ID="", CLOUDFLARE_API_TOKEN="", MARKETING_IMAGE_FALLBACK=False
)


@SEM_IMAGEM
class CampanhaTests(TestCase):
    def setUp(self):
        User = get_user_model()
        user = User.objects.create_user(username="mei@wageup.local", email="mei@wageup.local", password="x")
        UserProfile.objects.create(user=user, role="member")
        self.business = Business.objects.create(owner=user, name="Negocio")
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}")

    def _pedir(self):
        return self.client.post(
            "/api/marketing/chat/",
            {"prompt": "promover o bolo", "channel": "Instagram", "goal": "vender"},
            format="json",
        )

    @override_settings(ANTHROPIC_API_KEY="")
    def test_sem_chave_responde_com_o_texto_local(self):
        resposta = self._pedir()

        self.assertEqual(resposta.status_code, 201)
        self.assertTrue(resposta.data["message"])
        self.assertEqual(MarketingCampaign.objects.get().provider, "local-demo")

    @override_settings(ANTHROPIC_API_KEY="chave-invalida")
    @patch("apps.marketing.views._call_claude", side_effect=Exception("401 authentication_error"))
    def test_chave_invalida_cai_no_texto_local_em_vez_de_erro_500(self, _falha):
        resposta = self._pedir()

        # Antes esta chamada devolvia 500 e o usuario ficava sem campanha.
        self.assertEqual(resposta.status_code, 201)
        self.assertTrue(resposta.data["message"])
        self.assertEqual(MarketingCampaign.objects.get().provider, "local-demo")

    @override_settings(ANTHROPIC_API_KEY="chave-boa")
    @patch("apps.marketing.views._call_claude", return_value="Texto gerado pela IA")
    def test_com_chave_valida_usa_a_ia(self, _chamada):
        resposta = self._pedir()

        self.assertEqual(resposta.data["message"], "Texto gerado pela IA")
        self.assertEqual(MarketingCampaign.objects.get().provider, "anthropic")

    def test_sem_login_nao_gera_campanha(self):
        self.assertEqual(APIClient().post("/api/marketing/chat/", {}, format="json").status_code, 401)


@SEM_IMAGEM
class DadosDoProdutoTests(TestCase):
    """Os numeros da campanha saem do produto, nao do corpo da requisicao."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="mei@wageup.local", email="mei@wageup.local", password="x"
        )
        UserProfile.objects.create(user=self.user, role="member")
        self.business = Business.objects.create(owner=self.user, name="Negocio")
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.user).key}"
        )
        # Margem real: 100 - (40 + 10) - 11% de 100 = 39,00. Preco menos custo
        # daria 60,00, que e o erro que estes testes existem para travar.
        self.produto = Product.objects.create(
            business=self.business,
            name="Bolo de cenoura",
            price=Decimal("100"),
            cost=Decimal("40"),
            other_costs=Decimal("10"),
            fee_percent=Decimal("5"),
            tax_percent=Decimal("6"),
        )

    def _pedir(self, product=None):
        corpo = {"prompt": "promover", "channel": "Instagram", "goal": "promocao"}
        if product is not None:
            corpo["product"] = product
        return self.client.post("/api/marketing/chat/", corpo, format="json")

    @override_settings(ANTHROPIC_API_KEY="")
    def test_campanha_fica_vinculada_ao_produto(self):
        resposta = self._pedir({"id": str(self.produto.id)})

        campanha = MarketingCampaign.objects.get(id=resposta.data["campaign_id"])
        self.assertEqual(campanha.product, self.produto)

    @override_settings(ANTHROPIC_API_KEY="chave")
    @patch("apps.marketing.views.anthropic_sdk.Anthropic")
    def test_a_ia_recebe_a_margem_real_e_nao_preco_menos_custo(self, sdk):
        sdk.return_value.messages.create.return_value.content = [
            type("Bloco", (), {"text": "campanha"})()
        ]

        self._pedir({"id": str(self.produto.id)})

        enviado = sdk.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
        self.assertIn("Margem real por unidade: R$ 39.00", enviado)
        self.assertIn("Margem sobre o preço: 39.00%", enviado)
        self.assertNotIn("60.00", enviado)

    @override_settings(ANTHROPIC_API_KEY="chave")
    @patch("apps.marketing.views.anthropic_sdk.Anthropic")
    def test_numeros_do_corpo_sao_ignorados_quando_o_produto_existe(self, sdk):
        sdk.return_value.messages.create.return_value.content = [
            type("Bloco", (), {"text": "campanha"})()
        ]

        # Preco inflado no corpo: o cliente nao dita o que a IA recebe.
        self._pedir({"id": str(self.produto.id), "name": "Outro nome", "price": "999", "cost": "1"})

        enviado = sdk.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
        self.assertIn("Bolo de cenoura", enviado)
        self.assertIn("R$ 100.00", enviado)
        self.assertNotIn("999", enviado)

    @override_settings(ANTHROPIC_API_KEY="")
    def test_produto_de_outro_negocio_nao_e_usado(self):
        User = get_user_model()
        outro = User.objects.create_user(username="z@w.local", email="z@w.local", password="x")
        alheio = Product.objects.create(
            business=Business.objects.create(owner=outro, name="Outro"),
            name="Produto alheio",
            price=Decimal("50"),
            cost=Decimal("10"),
        )

        resposta = self._pedir({"id": str(alheio.id)})

        campanha = MarketingCampaign.objects.get(id=resposta.data["campaign_id"])
        self.assertIsNone(campanha.product)

    @override_settings(ANTHROPIC_API_KEY="")
    def test_preco_ilegivel_no_corpo_nao_derruba_a_rota(self):
        # Sem id, os numeros vem do corpo. "R$ 100,00" quebrava com 500.
        resposta = self._pedir({"name": "Bolo", "price": "R$ 100,00", "cost": "nao sei"})

        self.assertEqual(resposta.status_code, 201)
        self.assertTrue(resposta.data["message"])

    @override_settings(ANTHROPIC_API_KEY="")
    def test_product_que_nao_e_objeto_nao_derruba_a_rota(self):
        resposta = self._pedir("bolo")

        self.assertEqual(resposta.status_code, 201)


class RecomendacoesTests(TestCase):
    """As recomendacoes saem dos numeros do catalogo, com ou sem IA."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="mei@wageup.local", email="mei@wageup.local", password="x"
        )
        UserProfile.objects.create(user=self.user, role="member")
        self.business = Business.objects.create(owner=self.user, name="Negocio")
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.user).key}"
        )

    def _produto(self, nome, price, cost, **extra):
        return Product.objects.create(
            business=self.business,
            name=nome,
            price=Decimal(price),
            cost=Decimal(cost),
            **extra,
        )

    def _pedir(self):
        return self.client.get("/api/marketing/recommendations/")

    @override_settings(ANTHROPIC_API_KEY="")
    def test_sem_produto_orienta_cadastrar(self):
        resposta = self._pedir()

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.data["recommendations"]), 1)
        self.assertIn("catálogo", resposta.data["recommendations"][0]["title"].lower())

    @override_settings(ANTHROPIC_API_KEY="")
    def test_prejuizo_vira_recomendacao_de_rever_preco_nao_de_divulgar(self):
        # 50 - (45 + 10) - 11% de 50 = -10,50 por unidade.
        self._produto("Brigadeiro", "50", "45", other_costs="10", fee_percent="5", tax_percent="6")

        recomendacoes = self._pedir().data["recommendations"]

        primeira = recomendacoes[0]
        self.assertIn("preço", primeira["title"].lower())
        self.assertIn("prejuízo", primeira["text"].lower())

    @override_settings(ANTHROPIC_API_KEY="")
    def test_estoque_baixo_recomenda_repor_antes_de_divulgar(self):
        self._produto("Bolo", "100", "40", stock=2, min_stock=10)

        textos = " ".join(r["title"] + r["text"] for r in self._pedir().data["recommendations"])

        self.assertIn("Reponha", textos)

    @override_settings(ANTHROPIC_API_KEY="")
    def test_produto_nunca_divulgado_de_melhor_margem_vem_primeiro(self):
        bom = self._produto("Bolo caro", "200", "50", stock=30)
        self._produto("Bolo barato", "20", "15", stock=30)

        recomendacoes = self._pedir().data["recommendations"]

        self.assertEqual(recomendacoes[0]["product_id"], str(bom.id))
        self.assertEqual(recomendacoes[0]["goal"], "lancamento")

    @override_settings(ANTHROPIC_API_KEY="")
    def test_produto_ja_divulgado_nao_e_tratado_como_estreia(self):
        produto = self._produto("Bolo", "200", "50", stock=30)
        MarketingCampaign.objects.create(
            business=self.business, product=produto, prompt="p", channel="Instagram", goal="promocao"
        )

        titulos = [r["title"] for r in self._pedir().data["recommendations"]]

        self.assertNotIn("Estreie a divulgação", titulos)

    @override_settings(ANTHROPIC_API_KEY="")
    def test_produto_inativo_fica_fora(self):
        self._produto("Fora de linha", "500", "10", is_active=False)
        ativo = self._produto("Bolo", "100", "40")

        recomendacoes = self._pedir().data["recommendations"]

        ids = {r["product_id"] for r in recomendacoes}
        self.assertEqual(ids, {str(ativo.id)})

    @override_settings(ANTHROPIC_API_KEY="")
    def test_produto_de_outro_negocio_nao_entra(self):
        User = get_user_model()
        outro = User.objects.create_user(username="z@w.local", email="z@w.local", password="x")
        Product.objects.create(
            business=Business.objects.create(owner=outro, name="Outro"),
            name="Alheio", price=Decimal("999"), cost=Decimal("1"),
        )

        recomendacoes = self._pedir().data["recommendations"]

        self.assertNotIn("Alheio", " ".join(str(r) for r in recomendacoes))

    @override_settings(ANTHROPIC_API_KEY="chave")
    @patch("apps.marketing.recommendations.anthropic_sdk.Anthropic")
    def test_a_ia_recebe_a_margem_real_do_catalogo(self, sdk):
        sdk.return_value.messages.create.return_value.content = [
            type("Bloco", (), {"text": '[{"title": "T", "text": "X", "product_name": "Bolo", "channel": "WhatsApp", "goal": "promocao"}]'})()
        ]
        self._produto("Bolo", "100", "40", other_costs="10", fee_percent="5", tax_percent="6")

        resposta = self._pedir()

        enviado = sdk.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
        self.assertIn("margem real R$ 39,00", enviado)
        self.assertEqual(resposta.data["provider"], "anthropic")
        self.assertEqual(resposta.data["recommendations"][0]["channel"], "WhatsApp")

    @override_settings(ANTHROPIC_API_KEY="chave")
    @patch("apps.marketing.recommendations.anthropic_sdk.Anthropic")
    def test_produto_inventado_pela_ia_nao_vira_id(self, sdk):
        sdk.return_value.messages.create.return_value.content = [
            type("Bloco", (), {"text": '[{"title": "T", "text": "X", "product_name": "Produto que nao existe", "channel": "Instagram", "goal": "promocao"}]'})()
        ]
        self._produto("Bolo", "100", "40")

        recomendacoes = self._pedir().data["recommendations"]

        self.assertIsNone(recomendacoes[0]["product_id"])

    @override_settings(ANTHROPIC_API_KEY="chave")
    @patch("apps.marketing.recommendations.anthropic_sdk.Anthropic")
    def test_canal_e_objetivo_fora_da_lista_caem_no_padrao(self, sdk):
        sdk.return_value.messages.create.return_value.content = [
            type("Bloco", (), {"text": '[{"title": "T", "text": "X", "product_name": "Bolo", "channel": "LinkedIn", "goal": "viralizar"}]'})()
        ]
        self._produto("Bolo", "100", "40")

        recomendacao = self._pedir().data["recommendations"][0]

        self.assertEqual(recomendacao["channel"], "Instagram")
        self.assertEqual(recomendacao["goal"], "promocao")

    @override_settings(ANTHROPIC_API_KEY="chave")
    @patch("apps.marketing.recommendations.anthropic_sdk.Anthropic")
    def test_ia_fora_do_ar_cai_nas_regras_locais(self, sdk):
        sdk.return_value.messages.create.side_effect = RuntimeError("provedor fora")
        self._produto("Bolo", "100", "40")

        resposta = self._pedir()

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data["provider"], "local-demo")
        self.assertTrue(resposta.data["recommendations"])

    @override_settings(ANTHROPIC_API_KEY="chave")
    @patch("apps.marketing.recommendations.anthropic_sdk.Anthropic")
    def test_resposta_sem_json_cai_nas_regras_locais(self, sdk):
        sdk.return_value.messages.create.return_value.content = [
            type("Bloco", (), {"text": "Claro! Aqui vao minhas sugestoes..."})()
        ]
        self._produto("Bolo", "100", "40")

        self.assertTrue(self._pedir().data["recommendations"])

    def test_sem_login_nao_recomenda(self):
        self.assertEqual(APIClient().get("/api/marketing/recommendations/").status_code, 401)


PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _resposta_imagem(status_code=200, content=PNG, content_type="image/png", text=""):
    resposta = Mock(status_code=status_code, ok=200 <= status_code < 300, content=content)
    resposta.headers = {"Content-Type": content_type}
    resposta.text = text
    return resposta


class PromptDaImagemTests(SimpleTestCase):
    """O prompt da imagem sai da 'Ideia de imagem' que a campanha ja escreveu."""

    def test_extrai_a_ideia_de_imagem_do_texto(self):
        texto = (
            "**Chamada principal:** Bolo fresquinho\n\n"
            "**Ideia de imagem:** bolo de cenoura cortado ao meio, cobertura brilhando\n\n"
            "**Legenda:** Peca hoje\n\n"
            "**CTA:** Chame no direct"
        )

        prompt = extrair_prompt(texto, "Bolo", "Instagram")

        self.assertEqual(prompt, "bolo de cenoura cortado ao meio, cobertura brilhando")

    def test_funciona_sem_os_asteriscos_do_markdown(self):
        prompt = extrair_prompt("Ideia de imagem: torta em close\nLegenda: oi", "Torta", "WhatsApp")

        self.assertEqual(prompt, "torta em close")

    def test_sem_a_secao_monta_prompt_do_produto(self):
        prompt = extrair_prompt("Campanha sem essa secao", "Brigadeiro", "WhatsApp")

        self.assertIn("Brigadeiro", prompt)
        self.assertIn("WhatsApp", prompt)

    def test_texto_vazio_nao_quebra(self):
        self.assertIn("Bolo", extrair_prompt("", "Bolo", "Instagram"))


@override_settings(
    CLOUDFLARE_ACCOUNT_ID="conta", CLOUDFLARE_API_TOKEN="token", MARKETING_IMAGE_FALLBACK=True
)
class GeracaoDeImagemTests(SimpleTestCase):
    """Cloudflare primeiro, Pollinations depois, nada em vez de erro."""

    @patch("apps.marketing.images.requests.get")
    @patch("apps.marketing.images.requests.post")
    def test_usa_cloudflare_quando_ha_chave(self, post, get):
        post.return_value = _resposta_imagem()

        provider, conteudo, content_type = gerar_imagem("bolo em close")

        self.assertEqual(provider, "cloudflare")
        self.assertEqual(conteudo, PNG)
        self.assertEqual(content_type, "image/png")
        get.assert_not_called()
        self.assertIn("flux-1-schnell", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer token")
        # O prompt vai com o enquadramento em ingles em volta da ideia.
        self.assertIn("bolo em close", post.call_args.kwargs["json"]["prompt"])
        self.assertIn("product photography", post.call_args.kwargs["json"]["prompt"])

    @override_settings(CLOUDFLARE_ACCOUNT_ID="", CLOUDFLARE_API_TOKEN="")
    @patch("apps.marketing.images.requests.get")
    @patch("apps.marketing.images.requests.post")
    def test_sem_chave_da_cloudflare_vai_para_pollinations(self, post, get):
        get.return_value = _resposta_imagem(content_type="image/jpeg")

        provider, _, content_type = gerar_imagem("bolo")

        self.assertEqual(provider, "pollinations")
        self.assertEqual(content_type, "image/jpeg")
        post.assert_not_called()

    @patch("apps.marketing.images.requests.get")
    @patch("apps.marketing.images.requests.post")
    def test_cloudflare_fora_do_ar_cai_em_pollinations(self, post, get):
        post.side_effect = requests.Timeout()
        get.return_value = _resposta_imagem()

        provider, _, _ = gerar_imagem("bolo")

        self.assertEqual(provider, "pollinations")

    @patch("apps.marketing.images.requests.get")
    @patch("apps.marketing.images.requests.post")
    def test_cloudflare_respondendo_json_com_200_nao_vira_imagem(self, post, get):
        # Cota estourada devolve 200 com JSON. Gravar isso deixaria um texto
        # de erro no lugar da foto.
        post.return_value = _resposta_imagem(
            content=b'{"success": false}', content_type="application/json", text='{"success": false}'
        )
        get.return_value = _resposta_imagem()

        provider, conteudo, _ = gerar_imagem("bolo")

        self.assertEqual(provider, "pollinations")
        self.assertEqual(conteudo, PNG)

    @patch("apps.marketing.images.requests.get")
    @patch("apps.marketing.images.requests.post")
    def test_imagem_acima_do_limite_e_descartada(self, post, get):
        grande = b"0" * (400 * 1024 + 1)
        post.return_value = _resposta_imagem(content=grande)
        get.return_value = _resposta_imagem(content=grande)

        self.assertIsNone(gerar_imagem("bolo"))

    @patch("apps.marketing.images.requests.get", side_effect=requests.ConnectionError())
    @patch("apps.marketing.images.requests.post", side_effect=requests.ConnectionError())
    def test_todos_fora_do_ar_devolve_none(self, post, get):
        self.assertIsNone(gerar_imagem("bolo"))


class ImagemDaCampanhaTests(TestCase):
    """A campanha guarda a imagem e so o dono a acessa."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="mei@wageup.local", email="mei@wageup.local", password="x"
        )
        UserProfile.objects.create(user=self.user, role="member")
        self.business = Business.objects.create(owner=self.user, name="Negocio")
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.user).key}"
        )

    def _gerar(self):
        return self.client.post(
            "/api/marketing/chat/",
            {"prompt": "promover", "channel": "Instagram", "goal": "promocao"},
            format="json",
        )

    @override_settings(
        ANTHROPIC_API_KEY="", CLOUDFLARE_ACCOUNT_ID="", CLOUDFLARE_API_TOKEN="",
        MARKETING_IMAGE_FALLBACK=True,
    )
    @patch("apps.marketing.images.requests.get")
    def test_campanha_guarda_a_imagem_gerada(self, get):
        get.return_value = _resposta_imagem()

        resposta = self._gerar()

        self.assertTrue(resposta.data["has_image"])
        imagem = CampaignImage.objects.get(campaign__id=resposta.data["campaign_id"])
        self.assertEqual(bytes(imagem.data), PNG)
        self.assertEqual(imagem.provider, "pollinations")
        self.assertTrue(imagem.prompt)

    @override_settings(
        ANTHROPIC_API_KEY="", CLOUDFLARE_ACCOUNT_ID="", CLOUDFLARE_API_TOKEN="",
        MARKETING_IMAGE_FALLBACK=True,
    )
    @patch("apps.marketing.images.requests.get", side_effect=requests.ConnectionError())
    def test_provedor_fora_do_ar_nao_impede_a_campanha(self, get):
        resposta = self._gerar()

        self.assertEqual(resposta.status_code, 201)
        self.assertFalse(resposta.data["has_image"])
        self.assertTrue(resposta.data["message"])
        self.assertEqual(CampaignImage.objects.count(), 0)

    @override_settings(
        ANTHROPIC_API_KEY="", CLOUDFLARE_ACCOUNT_ID="", CLOUDFLARE_API_TOKEN="",
        MARKETING_IMAGE_FALLBACK=True,
    )
    @patch("apps.marketing.images.requests.get")
    def test_rota_serve_a_imagem_com_etag(self, get):
        get.return_value = _resposta_imagem()
        campaign_id = self._gerar().data["campaign_id"]

        resposta = self.client.get(f"/api/marketing/campaigns/{campaign_id}/image/")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"], "image/png")
        self.assertEqual(resposta.content, PNG)

        etag = resposta["ETag"]
        repetida = self.client.get(
            f"/api/marketing/campaigns/{campaign_id}/image/", HTTP_IF_NONE_MATCH=etag
        )
        self.assertEqual(repetida.status_code, 304)

    @override_settings(
        ANTHROPIC_API_KEY="", CLOUDFLARE_ACCOUNT_ID="", CLOUDFLARE_API_TOKEN="",
        MARKETING_IMAGE_FALLBACK=True,
    )
    @patch("apps.marketing.images.requests.get")
    def test_campanha_de_outro_negocio_nao_entrega_a_imagem(self, get):
        get.return_value = _resposta_imagem()
        campaign_id = self._gerar().data["campaign_id"]

        User = get_user_model()
        outro = User.objects.create_user(username="z@w.local", email="z@w.local", password="x")
        Business.objects.create(owner=outro, name="Outro")
        intruso = APIClient()
        intruso.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=outro).key}")

        resposta = intruso.get(f"/api/marketing/campaigns/{campaign_id}/image/")

        self.assertEqual(resposta.status_code, 404)

    def test_sem_login_nao_serve_imagem(self):
        resposta = APIClient().get(
            "/api/marketing/campaigns/00000000-0000-0000-0000-000000000000/image/"
        )

        self.assertEqual(resposta.status_code, 401)

    @override_settings(
        ANTHROPIC_API_KEY="", CLOUDFLARE_ACCOUNT_ID="", CLOUDFLARE_API_TOKEN="",
        MARKETING_IMAGE_FALLBACK=False,
    )
    @patch("apps.marketing.images.requests.get")
    @patch("apps.marketing.images.requests.post")
    def test_sem_provedor_configurado_nao_chama_ninguem(self, post, get):
        resposta = self._gerar()

        self.assertEqual(resposta.status_code, 201)
        self.assertFalse(resposta.data["has_image"])
        post.assert_not_called()
        get.assert_not_called()
