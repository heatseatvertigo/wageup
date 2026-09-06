from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import TransactionViewSet, statement_confirm, statement_preview

router = DefaultRouter()
router.register("", TransactionViewSet, basename="transaction")

# As rotas de importacao vem antes do router: registrado na raiz, ele trataria
# "import" como o id de uma transacao.
urlpatterns = [
    path("import/preview/", statement_preview, name="statement-preview"),
    path("import/confirm/", statement_confirm, name="statement-confirm"),
    *router.urls,
]
