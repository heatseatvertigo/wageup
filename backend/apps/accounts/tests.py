"""Testes da recuperacao de senha.

O runner do Django troca o EMAIL_BACKEND pelo de memoria, entao
`mail.outbox` guarda o que teria sido enviado.
"""
import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

User = get_user_model()

SENHA_ANTIGA = "senha-antiga-123"
SENHA_NOVA = "senha-nova-456"


class PasswordResetTests(APITestCase):
    def setUp(self):
        # O throttle de login conta no cache e e compartilhado entre testes.
        # Sem limpar, os ultimos testes da classe tomariam 429.
        cache.clear()
        self.user = User.objects.create_user(
            username="dono@wageup.local",
            email="dono@wageup.local",
            password=SENHA_ANTIGA,
            first_name="Dono",
        )
        self.request_url = reverse("password-reset")
        self.confirm_url = reverse("password-reset-confirm")

    def _pedir_link(self, email=None):
        resposta = self.client.post(
            self.request_url, {"email": email or self.user.email}, format="json"
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        return resposta

    def _uid_e_token(self):
        """Extrai uid e token do link do ultimo e-mail enviado."""
        corpo = mail.outbox[-1].body
        achado = re.search(r"\?uid=([^&\s]+)&token=([^\s]+)", corpo)
        self.assertIsNotNone(achado, f"link nao encontrado no e-mail:\n{corpo}")
        return achado.group(1), achado.group(2)

    def test_pedido_envia_email_com_link(self):
        self._pedir_link()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        uid, token = self._uid_e_token()
        self.assertTrue(uid and token)

    def test_email_desconhecido_responde_igual_e_nao_envia_nada(self):
        conhecido = self._pedir_link()
        mail.outbox.clear()

        desconhecido = self._pedir_link("ninguem@wageup.local")

        # Mesma resposta: a rota nao pode servir para descobrir quem tem conta.
        self.assertEqual(desconhecido.data, conhecido.data)
        self.assertEqual(len(mail.outbox), 0)

    def test_link_troca_a_senha(self):
        self._pedir_link()
        uid, token = self._uid_e_token()

        resposta = self.client.post(
            self.confirm_url,
            {"uid": uid, "token": token, "password": SENHA_NOVA},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(SENHA_NOVA))
        self.assertFalse(self.user.check_password(SENHA_ANTIGA))

    def test_troca_de_senha_invalida_o_token_de_autenticacao(self):
        antigo = Token.objects.create(user=self.user)
        self._pedir_link()
        uid, token = self._uid_e_token()

        self.client.post(
            self.confirm_url,
            {"uid": uid, "token": token, "password": SENHA_NOVA},
            format="json",
        )

        # Sessao anterior nao pode sobreviver ao reset.
        self.assertFalse(Token.objects.filter(key=antigo.key).exists())

    def test_link_nao_serve_duas_vezes(self):
        self._pedir_link()
        uid, token = self._uid_e_token()
        dados = {"uid": uid, "token": token, "password": SENHA_NOVA}
        self.client.post(self.confirm_url, dados, format="json")

        repetida = self.client.post(
            self.confirm_url, {**dados, "password": "outra-senha-789"}, format="json"
        )

        self.assertEqual(repetida.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(SENHA_NOVA))

    def test_token_invalido_recusado(self):
        self._pedir_link()
        uid, _ = self._uid_e_token()

        resposta = self.client.post(
            self.confirm_url,
            {"uid": uid, "token": "token-inventado", "password": SENHA_NOVA},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(SENHA_ANTIGA))

    def test_uid_corrompido_recusado_sem_erro_de_servidor(self):
        resposta = self.client.post(
            self.confirm_url,
            {"uid": "nao-e-base64", "token": "qualquer", "password": SENHA_NOVA},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_senha_curta_recusada(self):
        self._pedir_link()
        uid, token = self._uid_e_token()

        resposta = self.client.post(
            self.confirm_url,
            {"uid": uid, "token": token, "password": "curta"},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(SENHA_ANTIGA))

    def test_login_funciona_com_a_senha_nova(self):
        self._pedir_link()
        uid, token = self._uid_e_token()
        self.client.post(
            self.confirm_url,
            {"uid": uid, "token": token, "password": SENHA_NOVA},
            format="json",
        )

        resposta = self.client.post(
            reverse("login"),
            {"email": self.user.email, "password": SENHA_NOVA},
            format="json",
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertIn("token", resposta.data)
