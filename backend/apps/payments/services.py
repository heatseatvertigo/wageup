import requests
from django.conf import settings


class AbacatePayError(Exception):
    pass


class AbacatePayClient:
    base_url = "https://api.abacatepay.com/v2"

    def __init__(self, api_key=None):
        # strip(): espaco ou quebra de linha no fim da variavel de ambiente e
        # um erro comum de copiar/colar e quebraria o cabecalho Authorization.
        self.api_key = (api_key or settings.ABACATE_PAY_API_KEY or "").strip()

    def _validate_api_key(self):
        """Garante que a chave pode ir num cabecalho HTTP.

        Cabecalhos sao codificados em latin-1 pelo http.client. Uma chave com
        caractere fora de ASCII (tipico quando um hifen '-' vira travessao '—'
        ao copiar de um documento) estoura UnicodeEncodeError la no fundo da
        pilha do requests, sem indicar a causa. Melhor falhar aqui, claro.
        """
        if not self.api_key:
            raise AbacatePayError("ABACATE_PAY_API_KEY nao configurada.")

        invalid = [(i, c) for i, c in enumerate(self.api_key) if not c.isascii()]
        if invalid:
            position, char = invalid[0]
            raise AbacatePayError(
                f"ABACATE_PAY_API_KEY contem caractere invalido {char!r} "
                f"(U+{ord(char):04X}) na posicao {position}. "
                "Confira se algum hifen '-' virou travessao ao copiar a chave."
            )

    def create_pix_charge(self, *, amount_cents, description="", customer=None, metadata=None, expires_in=3600):
        self._validate_api_key()

        payload = {
            "method": "PIX",
            "data": {
                "amount": amount_cents,
                "description": description,
                "expiresIn": expires_in,
                "metadata": metadata or {},
            },
        }
        if customer:
            payload["data"]["customer"] = customer

        # Falhas de rede (timeout, DNS, conexao recusada) precisam virar
        # AbacatePayError: a view trata esse erro e responde 502. Sem isso a
        # excecao do requests escapa e o cliente recebe um 500 sem explicacao.
        try:
            response = requests.post(
                f"{self.base_url}/transparents/create",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=20,
            )
        except requests.Timeout as exc:
            raise AbacatePayError("A Abacate Pay nao respondeu em tempo. Tente novamente.") from exc
        except requests.RequestException as exc:
            raise AbacatePayError(f"Falha de conexao com a Abacate Pay: {exc}") from exc

        try:
            body = response.json()
        except ValueError as exc:
            raise AbacatePayError("Resposta invalida da Abacate Pay.") from exc

        if response.status_code >= 400 or body.get("error"):
            raise AbacatePayError(str(body.get("error") or body))

        return body.get("data") or {}
