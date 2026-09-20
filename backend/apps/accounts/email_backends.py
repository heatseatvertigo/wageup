"""Backend de e-mail do Django que entrega pela API HTTP do Resend.

Entra no lugar do SMTP: `send_mail` e o resto do codigo nao mudam, so a
entrega. A API HTTP e preferivel ao SMTP do Resend porque nao depende de
porta de saida liberada no host e devolve o erro em JSON legivel.

Sem dominio verificado no painel do Resend, a conta so consegue enviar para
o proprio e-mail do dono, a partir de `onboarding@resend.dev` — suficiente
para testar o fluxo. Para entregar a qualquer usuario e preciso verificar
um dominio e usar um remetente dele em DEFAULT_FROM_EMAIL.
"""
import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

RESEND_API_URL = "https://api.resend.com/emails"


class ResendError(Exception):
    pass


class ResendEmailBackend(BaseEmailBackend):
    def __init__(self, api_key=None, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        # strip(): mesmo cuidado do cliente da Abacate Pay — espaco ou quebra
        # de linha no fim da variavel quebraria o cabecalho Authorization.
        self.api_key = (api_key or settings.RESEND_API_KEY or "").strip()

    def send_messages(self, email_messages):
        enviados = 0
        for message in email_messages:
            if not message.recipients():
                continue
            try:
                self._send(message)
            except ResendError:
                if not self.fail_silently:
                    raise
            else:
                enviados += 1
        return enviados

    def _payload(self, message):
        payload = {
            "from": message.from_email,
            "to": list(message.to),
            "subject": message.subject,
            "text": message.body,
        }
        if message.cc:
            payload["cc"] = list(message.cc)
        if message.bcc:
            payload["bcc"] = list(message.bcc)
        if message.reply_to:
            payload["reply_to"] = list(message.reply_to)
        # EmailMultiAlternatives guarda a versao HTML em `alternatives`.
        for alternative in getattr(message, "alternatives", []):
            if alternative.mimetype == "text/html":
                payload["html"] = alternative.content
        return payload

    def _send(self, message):
        if not self.api_key:
            raise ResendError("RESEND_API_KEY nao configurada.")

        try:
            response = requests.post(
                RESEND_API_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=self._payload(message),
                timeout=20,
            )
        except requests.Timeout as exc:
            raise ResendError("O Resend nao respondeu em tempo.") from exc
        except requests.RequestException as exc:
            raise ResendError(f"Falha de conexao com o Resend: {exc}") from exc

        if response.ok:
            return

        # O Resend explica a recusa em JSON ("message"); sem isso, o corpo cru
        # ja ajuda mais do que so o status.
        try:
            detalhe = response.json().get("message") or response.text
        except ValueError:
            detalhe = response.text
        raise ResendError(f"Resend recusou o e-mail ({response.status_code}): {detalhe}")
