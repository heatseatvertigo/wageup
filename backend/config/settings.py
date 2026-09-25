from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent

env = environ.Env(
    # Default seguro: quem nao configurar nada roda com DEBUG desligado.
    # O .env.example liga DEBUG para desenvolvimento local.
    DJANGO_DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1", "testserver"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:5173", "http://127.0.0.1:5173"]),
    CSRF_TRUSTED_ORIGINS=(list, ["http://localhost:8000", "http://127.0.0.1:8000"]),
)
environ.Env.read_env(ROOT_DIR / ".env")


INSECURE_DEV_SECRET_KEY = "django-insecure-dev-wageup-change-me"
SECRET_KEY = env("SECRET_KEY", default=INSECURE_DEV_SECRET_KEY)

DEBUG = env("DJANGO_DEBUG")

# Uma SECRET_KEY conhecida ou curta permite forjar cookie de sessao e token de
# reset de senha. Em desenvolvimento a chave de exemplo e aceitavel; em
# producao nao. O minimo de 50 caracteres e o mesmo que o check --deploy do
# Django cobra (security.W009) — checar so a chave de exemplo deixaria passar
# um valor curto qualquer, que nao protege nada.
MIN_SECRET_KEY_LENGTH = 50

if not DEBUG and (
    SECRET_KEY == INSECURE_DEV_SECRET_KEY or len(SECRET_KEY) < MIN_SECRET_KEY_LENGTH
):
    raise ImproperlyConfigured(
        "SECRET_KEY ausente, de exemplo ou curta demais "
        f"(minimo {MIN_SECRET_KEY_LENGTH} caracteres). Gere uma com "
        "django.core.management.utils.get_random_secret_key() e defina a "
        "variavel de ambiente SECRET_KEY antes de subir com DJANGO_DEBUG=False."
    )

ALLOWED_HOSTS = env("ALLOWED_HOSTS")
# Dominios preenchidos automaticamente pela plataforma de deploy.
# Railway usa RAILWAY_PUBLIC_DOMAIN; Render usa RENDER_EXTERNAL_HOSTNAME.
PLATFORM_DOMAIN = env("RAILWAY_PUBLIC_DOMAIN", default="") or env("RENDER_EXTERNAL_HOSTNAME", default="")
if PLATFORM_DOMAIN:
    ALLOWED_HOSTS.append(PLATFORM_DOMAIN)


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework.authtoken',
    'apps.accounts',
    'apps.businesses',
    'apps.products',
    'apps.finance',
    'apps.payments',
    'apps.marketing',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")
if PLATFORM_DOMAIN:
    platform_origin = f"https://{PLATFORM_DOMAIN}"
    CORS_ALLOWED_ORIGINS.append(platform_origin)
    CSRF_TRUSTED_ORIGINS.append(platform_origin)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Fechado por padrao: uma view que esquecer de declarar permissao fica
    # inacessivel em vez de publica. As poucas rotas abertas (registro, login,
    # webhook, health check) declaram AllowAny explicitamente.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # A API navegavel do DRF expoe formularios e nomes de campos. Util em
    # desenvolvimento, desnecessaria em producao.
    "DEFAULT_RENDERER_CLASSES": (
        [
            "rest_framework.renderers.JSONRenderer",
            "rest_framework.renderers.BrowsableAPIRenderer",
        ]
        if DEBUG
        else ["rest_framework.renderers.JSONRenderer"]
    ),
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    # As rotas de IA custam dinheiro por chamada, entao tem limite proprio
    # ("ai"). "login" segura tentativa de descobrir senha por forca bruta.
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON", default="30/min"),
        "user": env("THROTTLE_USER", default="120/min"),
        "ai": env("THROTTLE_AI", default="60/hour"),
        "login": env("THROTTLE_LOGIN", default="10/min"),
    },
}

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}
# Reuso de conexao so faz sentido em Postgres (Neon/producao). Em SQLite local
# manter conexoes persistentes nao traz ganho e pode travar o arquivo, entao o
# ajuste e aplicado apenas quando o backend for PostgreSQL.
if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    DATABASES["default"]["CONN_MAX_AGE"] = 60
    DATABASES["default"]["CONN_HEALTH_CHECKS"] = True


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [ROOT_DIR / "frontend"]
STATIC_ROOT = ROOT_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Importacao de extrato bancario. O arquivo e lido em memoria e descartado:
# extrato e dado sensivel e a funcionalidade nao precisa dele depois que os
# lancamentos existem. Sem o handler de memoria como unico, o Django gravaria
# arquivos maiores num temporario em disco.
STATEMENT_MAX_UPLOAD_BYTES = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = STATEMENT_MAX_UPLOAD_BYTES
FILE_UPLOAD_HANDLERS = ["django.core.files.uploadhandler.MemoryFileUploadHandler"]

ABACATE_PAY_API_KEY = env("ABACATE_PAY_API_KEY", default="")
ABACATE_PAY_WEBHOOK_SECRET = env("ABACATE_PAY_WEBHOOK_SECRET", default="")
WAGEUP_ADMIN_EMAILS = env("WAGEUP_ADMIN_EMAILS", default="")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")

# Assistente financeiro. Sem chave, o endpoint responde localmente em vez
# de quebrar — mesmo padrao usado pelo marketing.
DEEPSEEK_API_KEY = env("DEEPSEEK_API_KEY", default="")
DEEPSEEK_BASE_URL = env("DEEPSEEK_BASE_URL", default="https://api.deepseek.com")
DEEPSEEK_MODEL = env("DEEPSEEK_MODEL", default="deepseek-chat")
GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID", default="")

# Geracao da imagem da campanha (apps/marketing/images.py). A Anthropic nao
# gera imagem, entao este e outro provedor. Sem as duas variaveis, o gerador
# cai no Pollinations, que nao pede chave; sem nenhum dos dois, a campanha sai
# sem imagem em vez de quebrar.
CLOUDFLARE_ACCOUNT_ID = env("CLOUDFLARE_ACCOUNT_ID", default="")
CLOUDFLARE_API_TOKEN = env("CLOUDFLARE_API_TOKEN", default="")

# O Pollinations nao pede chave, entao so a configuracao acima nao basta para
# decidir se ele roda: ligado por padrao, toda campanha esperaria por ele ate
# 45 segundos e sairia com marca d'agua. Fica opt-in — quem nao configurar
# nada gera campanha sem imagem, que e o comportamento util por default.
MARKETING_IMAGE_FALLBACK = env.bool("MARKETING_IMAGE_FALLBACK", default=False)

# ---------------------------------------------------------------------------
# E-mail (recuperacao de senha)
# ---------------------------------------------------------------------------
# Sem RESEND_API_KEY nem EMAIL_HOST a mensagem e impressa no console do
# runserver. O fluxo de recuperacao funciona inteiro em desenvolvimento sem
# depender de provedor de e-mail — mesmo padrao das chaves de IA, que caem
# para uma resposta local em vez de quebrar.
#
# Em producao, RESEND_API_KEY liga a entrega pela API HTTP do Resend
# (apps/accounts/email_backends.py); EMAIL_HOST, o SMTP generico. Sem uma
# das duas o link de recuperacao seria escrito no log do servidor e nunca
# chegaria ao usuario, que e uma falha silenciosa — por isso a escolha e
# explicita.
RESEND_API_KEY = env("RESEND_API_KEY", default="")
EMAIL_HOST = env("EMAIL_HOST", default="")
if RESEND_API_KEY:
    EMAIL_BACKEND = "apps.accounts.email_backends.ResendEmailBackend"
elif EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = env.int("EMAIL_PORT", default=587)
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
    EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="WageUp <nao-responda@wageup.local>")

# O default do Django e 3 dias. Duas horas e suficiente para quem pediu o
# link agora e reduz a janela em que um e-mail vazado ainda vale.
PASSWORD_RESET_TIMEOUT = env.int("PASSWORD_RESET_TIMEOUT", default=2 * 60 * 60)

CUSTOM_DOMAIN = env("CUSTOM_DOMAIN", default="")
if CUSTOM_DOMAIN:
    ALLOWED_HOSTS.append(CUSTOM_DOMAIN)
    CORS_ALLOWED_ORIGINS.append(f"https://{CUSTOM_DOMAIN}")
    CSRF_TRUSTED_ORIGINS.append(f"https://{CUSTOM_DOMAIN}")



# ---------------------------------------------------------------------------
# Seguranca de producao
# ---------------------------------------------------------------------------
# Cabecalhos que nao dependem de HTTPS valem sempre.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"

if not DEBUG:
    # O Render (e qualquer proxy TLS) entrega a requisicao ao gunicorn em HTTP
    # e informa o esquema original neste cabecalho. Sem isso o Django acha que
    # a conexao e insegura e o redirect de HTTPS entra em laco.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # HSTS fica gravado no navegador pelo tempo declarado e nao da para
    # cancelar antes disso. Por isso e ajustavel por variavel de ambiente:
    # comece baixo (ex.: 3600) ao estrear um dominio e suba depois.
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
    # Preload e irreversivel na pratica: so ligue com dominio proprio definitivo.
    SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# Sem esta configuracao os logs da aplicacao (ex.: falhas da Abacate Pay em
# apps/payments/views.py) nao aparecem na saida do gunicorn no Render.
LOG_LEVEL = env("LOG_LEVEL", default="INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}
