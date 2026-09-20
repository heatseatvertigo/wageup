"""Testes da recuperacao de senha.

O runner do Django troca o EMAIL_BACKEND pelo de memoria, entao
`mail.outbox` guarda o que teria sido enviado.
"""
import re
from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives, get_connection, send_mail
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .email_backends import ResendError

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


def _resposta_resend(status_code, body=None):
    resposta = Mock(status_code=status_code, ok=200 <= status_code < 300)
    resposta.json.return_value = body or {}
    resposta.text = str(body or "")
    return resposta


@override_settings(RESEND_API_KEY="re_teste", DEFAULT_FROM_EMAIL="WageUp <onboarding@resend.dev>")
class ResendBackendTests(SimpleTestCase):
    """O backend chama a API do Resend com o que o Django entregaria por SMTP."""

    BACKEND = "apps.accounts.email_backends.ResendEmailBackend"

    @patch("apps.accounts.email_backends.requests.post")
    def test_envia_pela_api_com_remetente_destino_e_corpo(self, post):
        post.return_value = _resposta_resend(200, {"id": "abc"})

        enviados = _enviar_pelo_backend(self.BACKEND, "Assunto", "Corpo", ["dono@wageup.local"])

        self.assertEqual(enviados, 1)
        post.assert_called_once()
        chamada = post.call_args
        self.assertEqual(chamada.args[0], "https://api.resend.com/emails")
        self.assertEqual(chamada.kwargs["headers"]["Authorization"], "Bearer re_teste")
        self.assertEqual(
            chamada.kwargs["json"],
            {
                "from": "WageUp <onboarding@resend.dev>",
                "to": ["dono@wageup.local"],
                "subject": "Assunto",
                "text": "Corpo",
            },
        )

    @patch("apps.accounts.email_backends.requests.post")
    def test_versao_html_vai_no_campo_html(self, post):
        post.return_value = _resposta_resend(200, {"id": "abc"})
        mensagem = EmailMultiAlternatives(
            "Assunto", "texto", to=["dono@wageup.local"], connection=get_connection(self.BACKEND)
        )
        mensagem.attach_alternative("<p>html</p>", "text/html")
        mensagem.send()

        self.assertEqual(post.call_args.kwargs["json"]["html"], "<p>html</p>")

    @patch("apps.accounts.email_backends.requests.post")
    def test_recusa_da_api_vira_erro_com_a_explicacao(self, post):
        post.return_value = _resposta_resend(403, {"message": "domain is not verified"})
        with self.assertRaisesRegex(ResendError, "403.*domain is not verified"):
            _enviar_pelo_backend(self.BACKEND, "Assunto", "Corpo", ["dono@wageup.local"])

    @patch("apps.accounts.email_backends.requests.post", side_effect=requests.Timeout())
    def test_timeout_vira_erro_ou_e_engolido_com_fail_silently(self, post):
        with self.assertRaises(ResendError):
            _enviar_pelo_backend(self.BACKEND, "Assunto", "Corpo", ["dono@wageup.local"])

        enviados = _enviar_pelo_backend(
            self.BACKEND, "Assunto", "Corpo", ["dono@wageup.local"], fail_silently=True
        )
        self.assertEqual(enviados, 0)

    @override_settings(RESEND_API_KEY="")
    def test_sem_chave_falha_claro_em_vez_de_chamar_a_api(self):
        with patch("apps.accounts.email_backends.requests.post") as post:
            with self.assertRaisesRegex(ResendError, "RESEND_API_KEY"):
                _enviar_pelo_backend(self.BACKEND, "Assunto", "Corpo", ["dono@wageup.local"])
        post.assert_not_called()


def _enviar_pelo_backend(backend, assunto, corpo, destinatarios, fail_silently=False):
    return send_mail(
        assunto,
        corpo,
        None,
        destinatarios,
        fail_silently=fail_silently,
        connection=get_connection(backend, fail_silently=fail_silently),
    )
