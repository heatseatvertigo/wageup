from django.conf import settings
from django.http import HttpResponse
from django.views.static import serve
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

# Arquivos do frontend que recebem versao na URL.
VERSIONED_ASSETS = ("styles.css", "app.js", "a11y.js", "site.js")


@api_view(["GET"])
@permission_classes([AllowAny])
# Sem throttle: o Render consulta esta rota para saber se o servico esta vivo.
# Um 429 aqui derrubaria o deploy.
@throttle_classes([])
def health_check(request):
    return Response({"status": "ok", "service": "wageup-api"})


def _asset_version(path):
    """Versao do arquivo, derivada da data de modificacao."""
    try:
        return str(int(path.stat().st_mtime))
    except OSError:
        return "0"


def frontend_asset(request, path):
    """CSS e JS do frontend. Com ?v= na URL (o index sempre manda), o navegador
    guarda por um ano: o arquivo nunca muda sob a mesma versao, porque a versao
    vem da data de modificacao. Sem isto, cada visita baixava os quatro
    arquivos de novo pelo servidor, que no plano free atende devagar."""
    resposta = serve(request, path, document_root=settings.ROOT_DIR / "frontend")
    if request.GET.get("v") and resposta.status_code == 200:
        resposta["Cache-Control"] = "public, max-age=31536000, immutable"
    return resposta


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

    response = HttpResponse(content, content_type="text/html; charset=utf-8")
    # O HTML nunca pode vir do cache: e ele que carrega as URLs versionadas do
    # CSS e do JS. Guardado, o navegador continua pedindo os arquivos antigos e
    # monta a pagina nova sobre estilos velhos.
    response["Cache-Control"] = "no-cache, must-revalidate"
    return response
