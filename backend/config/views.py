from django.conf import settings
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def health_check(request):
    return Response({"status": "ok", "service": "wageup-api"})


def frontend_index(request):
    html_path = settings.ROOT_DIR / "frontend" / "index.html"
    content = html_path.read_text(encoding="utf-8")
    inject = (
        f'<script>'
        f'window.WAGEUP_GOOGLE_CLIENT_ID = "{settings.GOOGLE_CLIENT_ID}";'
        f'window.WAGEUP_API_URL = "/api";'
        f'</script>'
    )
    content = content.replace("</head>", f"{inject}\n</head>", 1)
    return HttpResponse(content, content_type="text/html; charset=utf-8")
