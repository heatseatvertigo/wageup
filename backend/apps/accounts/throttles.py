"""Limites de requisicao por rota.

O DRF le a taxa a partir do atributo `scope` da classe, e as taxas em si
ficam em REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] no settings.

Estas subclasses existem porque `ScopedRateThrottle` depende de um atributo
`throttle_scope` na view, e views criadas com o decorador `@api_view` nao
carregam atributos arbitrarios. Uma classe por escopo resolve sem gambiarra.
"""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Registro e login. Segura tentativa de descobrir senha por forca bruta."""

    scope = "login"


class AIRateThrottle(UserRateThrottle):
    """Rotas que chamam modelo de linguagem. Cada chamada custa dinheiro."""

    scope = "ai"
