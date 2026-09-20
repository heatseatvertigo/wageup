"""Testes da geracao de campanha.

O ponto coberto aqui e o caminho de falha: chave invalida ou provedor fora do
ar nao pode deixar o usuario sem campanha nenhuma.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import UserProfile
from apps.businesses.models import Business

from .models import MarketingCampaign


class CampanhaTests(TestCase):
    def setUp(self):
        User = get_user_model()
        user = User.objects.create_user(username="mei@wageup.local", email="mei@wageup.local", password="x")
        UserProfile.objects.create(user=user, role="member")
        Business.objects.create(owner=user, name="Negocio")
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
