"""Testes da geracao de campanha.

Dois pontos: o caminho de falha (chave invalida ou provedor fora do ar nao
pode deixar o usuario sem campanha nenhuma) e os numeros que vao para a IA,
que saem do produto no banco e nao do corpo da requisicao.
"""
import base64
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
    CLOUDFLARE_ACCOUNT_ID="", CLOUDFLARE_API_TOKEN="", MARKETING_IMAGE_FALLBACK=False,
    # Sem DeepSeek por padrao: os testes que querem um provedor ligam o seu.
    DEEPSEEK_API_KEY="",
)


def _texto(texto):
    """Resposta falsa do SDK da Anthropic com o texto dado."""
    return [type("Bloco", (), {"text": texto})()]


CAMPANHA_DA_IA = (
    "**Chamada principal:** Bolo quentinho\n"
    "**Ideia de imagem:** bolo sobre mesa de madeira, luz de janela\n"
    "**Legenda:** Hoje tem bolo!\n"
    "**CTA:** Chama no direct"
)


class _ChatBase(TestCase):
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

    def _pedir(self, mensagem="cria um post do bolo de cenoura", conversation_id=None):
        corpo = {"message": mensagem}
        if conversation_id:
            corpo["conversation_id"] = conversation_id
        return self.client.post("/api/marketing/chat/", corpo, format="json")


@SEM_IMAGEM
class ChatDeMarketingTests(_ChatBase):
    """O usuario escreve o pedido que quiser; a falha do provedor nao o deixa sem resposta."""

    @override_settings(ANTHROPIC_API_KEY="")
    def test_sem_chave_responde_com_o_texto_local(self):
        resposta = self._pedir()

        self.assertEqual(resposta.status_code, 201)
        self.assertIn("Bolo de cenoura", resposta.data["message"])
        self.assertEqual(MarketingCampaign.objects.get().provider, "local-demo")

    @override_settings(ANTHROPIC_API_KEY="chave-invalida")
    @patch("apps.marketing.assistant._call_claude", side_effect=Exception("401 authentication_error"))
    def test_chave_invalida_cai_no_texto_local_em_vez_de_erro_500(self, _falha):
        resposta = self._pedir()

        self.assertEqual(resposta.status_code, 201)
        self.assertTrue(resposta.data["message"])
        self.assertEqual(resposta.data["provider"], "local-demo")

    @override_settings(ANTHROPIC_API_KEY="chave-boa")
    @patch("apps.marketing.assistant._call_claude", return_value=CAMPANHA_DA_IA)
    def test_campanha_da_ia_vira_registro_ligado_ao_produto_citado(self, _chamada):
        resposta = self._pedir("faz um post do bolo de cenoura pro whatsapp")

        campanha = MarketingCampaign.objects.get(id=resposta.data["campaign_id"])
        self.assertEqual(campanha.provider, "anthropic")
        self.assertEqual(campanha.product, self.produto)
        self.assertEqual(campanha.channel, "WhatsApp")
        self.assertEqual(campanha.generated_text, CAMPANHA_DA_IA)

    @override_settings(ANTHROPIC_API_KEY="chave-boa")
    @patch("apps.marketing.assistant._call_claude", return_value="#bolo #confeitaria #docesfeitosamao")
    def test_resposta_que_nao_e_campanha_nao_vira_registro(self, _chamada):
        resposta = self._pedir("me passa hashtags boas")

        self.assertEqual(resposta.status_code, 201)
        self.assertIsNone(resposta.data["campaign_id"])
        self.assertFalse(resposta.data["has_image"])
        self.assertEqual(MarketingCampaign.objects.count(), 0)

    def test_mensagem_vazia_e_recusada(self):
        self.assertEqual(self._pedir("   ").status_code, 400)

    def test_sem_login_nao_gera_campanha(self):
        self.assertEqual(APIClient().post("/api/marketing/chat/", {}, format="json").status_code, 401)


@SEM_IMAGEM
class RespostaLocalTests(_ChatBase):
    """Sem IA, a resposta local fala do que foi pedido e diz por que e local."""

    @override_settings(ANTHROPIC_API_KEY="")
    def test_sem_produto_citado_usa_o_assunto_do_pedido(self):
        resposta = self._pedir("faca uma foto com um post para o meu novo anuncio de pudim")

        self.assertIn("garantir pudim", resposta.data["message"])
        self.assertNotIn("Bolo de cenoura", resposta.data["message"])
        self.assertIn("falta a DEEPSEEK_API_KEY", resposta.data["message"])
        # O assunto chega ao prompt da imagem pela "Ideia de imagem".
        campanha = MarketingCampaign.objects.get(id=resposta.data["campaign_id"])
        self.assertIsNone(campanha.product)
        self.assertIn("foto clara de pudim", campanha.generated_text)

    @override_settings(ANTHROPIC_API_KEY="chave")
    @patch("apps.marketing.assistant._call_claude", side_effect=Exception("timeout"))
    def test_falha_da_ia_nao_diz_que_falta_configurar(self, _falha):
        resposta = self._pedir()

        self.assertIn("não respondeu agora", resposta.data["message"])
        self.assertNotIn("falta a DEEPSEEK_API_KEY", resposta.data["message"])

    @override_settings(ANTHROPIC_API_KEY="", DEEPSEEK_API_KEY="")
    def test_assunto_novo_na_conversa_nao_herda_o_produto_anterior(self):
        conversa = self._pedir("post do bolo de cenoura").data["conversation"]["id"]

        resposta = self._pedir(
            "crie um post com imagem para anunciar meu cachorro quente", conversation_id=conversa
        )

        self.assertIn("cachorro quente", resposta.data["message"])
        self.assertNotIn("Bolo de cenoura", resposta.data["message"])
        campanha = MarketingCampaign.objects.get(id=resposta.data["campaign_id"])
        self.assertIsNone(campanha.product)

    def test_assunto_do_pedido(self):
        from .assistant import assunto_do_pedido

        casos = {
            "faca uma foto com um post para o meu novo anuncio de pudim": "pudim",
            "Crie um post para o Instagram divulgando Bolo de cenoura": "Bolo de cenoura",
            "campanha de lançamento da torta de limão": "torta de limão",
            "quero vender meu brownie no instagram": "brownie",
            "me dá 5 ideias de vídeos curtos para o TikTok": None,
        }
        for pedido, esperado in casos.items():
            with self.subTest(pedido=pedido):
                self.assertEqual(assunto_do_pedido(pedido), esperado)


@SEM_IMAGEM
class ProvedoresTests(_ChatBase):
    """DeepSeek primeiro, como no assistente financeiro; Anthropic como alternativa."""

    @override_settings(DEEPSEEK_API_KEY="chave-deepseek", ANTHROPIC_API_KEY="chave-anthropic")
    @patch("apps.marketing.assistant._call_claude")
    @patch("apps.marketing.assistant._call_deepseek", return_value=CAMPANHA_DA_IA)
    def test_usa_a_deepseek_quando_ha_chave(self, deepseek, claude):
        resposta = self._pedir()

        self.assertEqual(resposta.data["provider"], "deepseek")
        claude.assert_not_called()
        # A primeira chamada e a do chat; a segunda traduz a ideia de imagem.
        system, history = deepseek.call_args_list[0].args
        self.assertIn("margem real R$ 39,00", system)
        self.assertEqual(history[-1]["content"], "cria um post do bolo de cenoura")

    @override_settings(DEEPSEEK_API_KEY="chave-deepseek", ANTHROPIC_API_KEY="chave-anthropic")
    @patch("apps.marketing.assistant._call_claude", return_value=CAMPANHA_DA_IA)
    @patch("apps.marketing.assistant._call_deepseek", side_effect=Exception("502"))
    def test_deepseek_fora_do_ar_tenta_a_anthropic(self, _deepseek, _claude):
        self.assertEqual(self._pedir().data["provider"], "anthropic")

    @override_settings(DEEPSEEK_API_KEY="chave-deepseek", ANTHROPIC_API_KEY="")
    @patch("apps.marketing.assistant._call_deepseek", side_effect=Exception("401"))
    def test_so_deepseek_e_ela_falha_cai_na_resposta_local(self, _deepseek):
        resposta = self._pedir()

        self.assertEqual(resposta.data["provider"], "local-demo")
        self.assertIn("não respondeu agora", resposta.data["message"])


@SEM_IMAGEM
class ContextoDaIaTests(_ChatBase):
    """Os numeros que a IA recebe saem do catalogo, nao do cliente."""

    @override_settings(ANTHROPIC_API_KEY="chave")
    @patch("apps.marketing.assistant.anthropic_sdk.Anthropic")
    def test_a_ia_recebe_o_catalogo_com_a_margem_real(self, sdk):
        sdk.return_value.messages.create.return_value.content = _texto("ok")

        self._pedir("o que eu divulgo essa semana?")

        system = sdk.return_value.messages.create.call_args.kwargs["system"]
        self.assertIn("Bolo de cenoura", system)
        self.assertIn("margem real R$ 39,00", system)
        self.assertNotIn("60,00", system)

    @override_settings(ANTHROPIC_API_KEY="chave")
    @patch("apps.marketing.assistant.anthropic_sdk.Anthropic")
    def test_produto_de_outro_negocio_nao_entra_no_contexto(self, sdk):
        sdk.return_value.messages.create.return_value.content = _texto("ok")
        User = get_user_model()
        outro = User.objects.create_user(username="z@w.local", email="z@w.local", password="x")
        Product.objects.create(
            business=Business.objects.create(owner=outro, name="Outro"),
            name="Produto alheio",
            price=Decimal("50"),
            cost=Decimal("10"),
        )

        self._pedir("cria um post do Produto alheio")

        system = sdk.return_value.messages.create.call_args.kwargs["system"]
        self.assertNotIn("Produto alheio", system)

    @override_settings(ANTHROPIC_API_KEY="chave")
    @patch("apps.marketing.assistant.anthropic_sdk.Anthropic")
    def test_historico_vem_do_banco_e_segue_a_conversa(self, sdk):
        sdk.return_value.messages.create.return_value.content = _texto(CAMPANHA_DA_IA)
        primeira = self._pedir("post do bolo de cenoura pro whatsapp")
        conversa = primeira.data["conversation"]["id"]

        sdk.return_value.messages.create.return_value.content = _texto(CAMPANHA_DA_IA)
        segunda = self._pedir("agora mais curto", conversation_id=conversa)

        # Cada campanha faz duas chamadas: o chat e a traducao da ideia de
        # imagem. A do chat da segunda campanha e a penultima.
        enviado = sdk.return_value.messages.create.call_args_list[-2].kwargs["messages"]
        self.assertEqual([m["role"] for m in enviado], ["user", "assistant", "user"])
        self.assertEqual(enviado[-1]["content"], "agora mais curto")
        # Sem citar produto nem canal, herda os da campanha anterior.
        campanha = MarketingCampaign.objects.get(id=segunda.data["campaign_id"])
        self.assertEqual(campanha.product, self.produto)
        self.assertEqual(campanha.channel, "WhatsApp")


@SEM_IMAGEM
class ConversasTests(_ChatBase):
    @override_settings(ANTHROPIC_API_KEY="")
    def test_lista_e_abre_a_conversa(self):
        conversa = self._pedir().data["conversation"]

        lista = self.client.get("/api/marketing/conversations/")
        self.assertEqual([c["id"] for c in lista.data], [conversa["id"]])
        self.assertEqual(lista.data[0]["title"], "cria um post do bolo de cenoura")

        detalhe = self.client.get(f"/api/marketing/conversations/{conversa['id']}/")
        self.assertEqual([m["role"] for m in detalhe.data["messages"]], ["user", "assistant"])
        self.assertTrue(detalhe.data["messages"][1]["campaign_id"])

    @override_settings(ANTHROPIC_API_KEY="")
    def test_conversa_de_outro_negocio_nao_abre_nem_continua(self):
        conversa = self._pedir().data["conversation"]["id"]
        User = get_user_model()
        outro = User.objects.create_user(username="z@w.local", email="z@w.local", password="x")
        Business.objects.create(owner=outro, name="Outro")
        intruso = APIClient()
        intruso.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=outro).key}")

        self.assertEqual(intruso.get(f"/api/marketing/conversations/{conversa}/").status_code, 404)
        self.assertEqual(intruso.delete(f"/api/marketing/conversations/{conversa}/").status_code, 404)
        resposta = intruso.post(
            "/api/marketing/chat/", {"message": "oi", "conversation_id": conversa}, format="json"
        )
        self.assertNotEqual(resposta.data["conversation"]["id"], conversa)

    @override_settings(ANTHROPIC_API_KEY="")
    def test_conversation_id_invalido_comeca_conversa_nova(self):
        resposta = self._pedir(conversation_id="nao-e-uuid")

        self.assertEqual(resposta.status_code, 201)

    @override_settings(ANTHROPIC_API_KEY="")
    def test_apagar_conversa_mantem_a_campanha(self):
        conversa = self._pedir().data["conversation"]["id"]

        self.assertEqual(self.client.delete(f"/api/marketing/conversations/{conversa}/").status_code, 204)
        self.assertEqual(MarketingCampaign.objects.count(), 1)

    def test_sem_login_nao_lista(self):
        self.assertEqual(APIClient().get("/api/marketing/conversations/").status_code, 401)


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
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64


def _resposta_cloudflare(status_code=200, imagem=JPEG, corpo=None, text=""):
    """A Cloudflare responde JSON com a imagem em base64, nao os bytes crus."""
    resposta = Mock(status_code=status_code, ok=200 <= status_code < 300)
    if corpo is None:
        corpo = {"success": True, "result": {"image": base64.b64encode(imagem).decode()}}
    resposta.json.return_value = corpo
    resposta.text = text
    return resposta


def _resposta_pollinations(status_code=200, content=PNG, content_type="image/png"):
    """O Pollinations devolve os bytes da imagem direto no corpo."""
    resposta = Mock(status_code=status_code, ok=200 <= status_code < 300, content=content)
    resposta.headers = {"Content-Type": content_type}
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
        post.return_value = _resposta_cloudflare()

        provider, conteudo, content_type = gerar_imagem("bolo em close")

        self.assertEqual(provider, "cloudflare")
        self.assertEqual(conteudo, JPEG)
        self.assertEqual(content_type, "image/jpeg")
        get.assert_not_called()
        self.assertIn("flux-1-schnell", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer token")
        # O prompt vai com o enquadramento em ingles em volta da ideia, e o
        # produto passa pelo glossario.
        self.assertIn("cake em close", post.call_args.kwargs["json"]["prompt"])
        self.assertIn("advertising photo", post.call_args.kwargs["json"]["prompt"])

    @patch("apps.marketing.images.requests.post")
    def test_nao_manda_largura_e_altura_para_a_cloudflare(self, post):
        # O FLUX.1-schnell recusa a requisicao inteira com 400 se receber
        # width ou height: "Additional or unevaluated properties not allowed".
        post.return_value = _resposta_cloudflare()

        gerar_imagem("bolo")

        self.assertEqual(set(post.call_args.kwargs["json"]), {"prompt"})

    @override_settings(CLOUDFLARE_ACCOUNT_ID="", CLOUDFLARE_API_TOKEN="")
    @patch("apps.marketing.images.requests.get")
    @patch("apps.marketing.images.requests.post")
    def test_sem_chave_da_cloudflare_vai_para_pollinations(self, post, get):
        get.return_value = _resposta_pollinations(content_type="image/jpeg")

        provider, _, content_type = gerar_imagem("bolo")

        self.assertEqual(provider, "pollinations")
        self.assertEqual(content_type, "image/jpeg")
        post.assert_not_called()

    @patch("apps.marketing.images.requests.get")
    @patch("apps.marketing.images.requests.post")
    def test_cloudflare_fora_do_ar_cai_em_pollinations(self, post, get):
        post.side_effect = requests.Timeout()
        get.return_value = _resposta_pollinations()

        provider, _, _ = gerar_imagem("bolo")

        self.assertEqual(provider, "pollinations")

    @patch("apps.marketing.images.requests.get")
    @patch("apps.marketing.images.requests.post")
    def test_cloudflare_com_success_false_nao_vira_imagem(self, post, get):
        # Cota estourada ou token sem permissao volta 200 com success false.
        # Sem conferir, o base64 ausente viraria imagem vazia.
        post.return_value = _resposta_cloudflare(
            corpo={"success": False, "errors": [{"message": "out of neurons"}], "result": None}
        )
        get.return_value = _resposta_pollinations()

        provider, conteudo, _ = gerar_imagem("bolo")

        self.assertEqual(provider, "pollinations")
        self.assertEqual(conteudo, PNG)

    @patch("apps.marketing.images.requests.get")
    @patch("apps.marketing.images.requests.post")
    def test_base64_invalido_da_cloudflare_nao_vira_imagem(self, post, get):
        post.return_value = _resposta_cloudflare(corpo={"success": True, "result": {"image": "nao!!"}})
        get.return_value = _resposta_pollinations()

        provider, _, _ = gerar_imagem("bolo")

        self.assertEqual(provider, "pollinations")

    @patch("apps.marketing.images.requests.get")
    @patch("apps.marketing.images.requests.post")
    def test_imagem_acima_do_limite_e_descartada(self, post, get):
        grande = b"0" * (1024 * 1024 + 1)
        post.return_value = _resposta_cloudflare(imagem=grande)
        get.return_value = _resposta_pollinations(content=grande)

        self.assertIsNone(gerar_imagem("bolo"))

    @patch("apps.marketing.images.requests.get")
    @patch("apps.marketing.images.requests.post")
    def test_jpeg_de_1024_do_flux_cabe_no_limite(self, post, get):
        # O FLUX devolve por volta de 540 KB, acima do teto de 400 KB da foto
        # de produto. Este caso trava o teto em algo que a imagem real cabe.
        real = b"0" * (600 * 1024)
        post.return_value = _resposta_cloudflare(imagem=real)

        provider, conteudo, _ = gerar_imagem("bolo")

        self.assertEqual(provider, "cloudflare")
        self.assertEqual(len(conteudo), len(real))
        get.assert_not_called()

    @patch("apps.marketing.images.requests.get", side_effect=requests.ConnectionError())
    @patch("apps.marketing.images.requests.post", side_effect=requests.ConnectionError())
    def test_todos_fora_do_ar_devolve_none(self, post, get):
        self.assertIsNone(gerar_imagem("bolo"))


class PromptEmInglesTests(SimpleTestCase):
    """O FLUX le ao pe da letra: "cachorro quente" desenhava um cachorro."""

    def test_glossario_traduz_o_produto(self):
        from .images import traduzir_termos

        traduzido = traduzir_termos("foto clara de cachorro quente sobre uma mesa")
        self.assertIn("Brazilian hot dog", traduzido)
        self.assertNotIn("cachorro", traduzido)

    @patch("apps.marketing.images.requests.get")
    @override_settings(CLOUDFLARE_ACCOUNT_ID="", CLOUDFLARE_API_TOKEN="", MARKETING_IMAGE_FALLBACK=True)
    def test_prompt_pronto_so_ganha_as_travas(self, get):
        get.return_value = _resposta_pollinations()

        gerar_imagem("juicy Brazilian hot dog, dark background", pronto=True)

        url = get.call_args.args[0]
        self.assertIn("juicy%20Brazilian%20hot%20dog", url)
        self.assertIn("no%20text", url)
        self.assertNotIn("appetizing%20advertising", url)

    @override_settings(DEEPSEEK_API_KEY="chave", ANTHROPIC_API_KEY="")
    @patch("apps.marketing.assistant._call_deepseek", return_value="Brazilian hot dog hero shot, steam")
    def test_ia_de_texto_traduz_a_ideia(self, deepseek):
        from .assistant import prompt_da_imagem

        self.assertEqual(
            prompt_da_imagem("foto de cachorro quente", "cachorro quente"),
            "Brazilian hot dog hero shot, steam",
        )
        self.assertIn("cachorro quente", deepseek.call_args.args[1][0]["content"])

    @override_settings(DEEPSEEK_API_KEY="", ANTHROPIC_API_KEY="")
    def test_sem_ia_de_texto_devolve_none(self):
        from .assistant import prompt_da_imagem

        self.assertIsNone(prompt_da_imagem("foto de pudim"))


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
            "/api/marketing/chat/", {"message": "cria uma campanha para o Instagram"}, format="json"
        )

    @override_settings(
        ANTHROPIC_API_KEY="", CLOUDFLARE_ACCOUNT_ID="", CLOUDFLARE_API_TOKEN="",
        MARKETING_IMAGE_FALLBACK=True,
    )
    @patch("apps.marketing.images.requests.get")
    def test_campanha_guarda_a_imagem_gerada(self, get):
        get.return_value = _resposta_pollinations()

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
        get.return_value = _resposta_pollinations()
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
        get.return_value = _resposta_pollinations()
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
