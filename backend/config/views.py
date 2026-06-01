from pathlib import Path

from django.conf import settings
from django.http import FileResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def health_check(request):
    return Response({"status": "ok", "service": "wageup-api"})


def frontend_index(request):
    return FileResponse(open(settings.ROOT_DIR / "frontend" / "index.html", "rb"))
