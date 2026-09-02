from django.conf import settings
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response

# Arquivos do frontend que recebem versao na URL.
VERSIONED_ASSETS = ("styles.css", "app.js")


@api_view(["GET"])
def health_check(request):
    return Response({"status": "ok", "service": "wageup-api"})


def _asset_version(path):
    """Versao do arquivo, derivada da data de modificacao."""
    try:
        return str(int(path.stat().st_mtime))
    except OSError:
        return "0"


def frontend_index(request):
    frontend_dir = settings.ROOT_DIR / "frontend"
    content = (frontend_dir / "index.html").read_text(encoding="utf-8")

    # Sem versao na URL, o navegador reaproveita o CSS e o JS antigos e monta
    # a pagina com HTML novo sobre estilos velhos — o layout quebra de formas
    # dificeis de diagnosticar. A versao muda junto com o arquivo, entao cada
    # deploy invalida o cache sozinho.
    for asset in VERSIONED_ASSETS:
        version = _asset_version(frontend_dir / asset)
        content = content.replace(f'"{asset}"', f'"{asset}?v={version}"')

    inject = (
        f'<script>'
        f'window.WAGEUP_GOOGLE_CLIENT_ID = "{settings.GOOGLE_CLIENT_ID}";'
        f'window.WAGEUP_API_URL = "/api";'
        f'</script>'
    )
    content = content.replace("</head>", f"{inject}\n</head>", 1)
    return HttpResponse(content, content_type="text/html; charset=utf-8")
