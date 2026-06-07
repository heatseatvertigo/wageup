import requests
from django.conf import settings


class AbacatePayError(Exception):
    pass


class AbacatePayClient:
    base_url = "https://api.abacatepay.com/v2"

    def __init__(self, api_key=None):
        self.api_key = api_key or settings.ABACATE_PAY_API_KEY

    def create_pix_charge(self, *, amount_cents, description="", customer=None, metadata=None, expires_in=3600):
        if not self.api_key:
            raise AbacatePayError("ABACATE_PAY_API_KEY nao configurada.")

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

        response = requests.post(
            f"{self.base_url}/transparents/create",
            json=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=20,
        )

        try:
            body = response.json()
        except ValueError as exc:
            raise AbacatePayError("Resposta invalida da Abacate Pay.") from exc

        if response.status_code >= 400 or body.get("error"):
            raise AbacatePayError(str(body.get("error") or body))

        return body.get("data") or {}
