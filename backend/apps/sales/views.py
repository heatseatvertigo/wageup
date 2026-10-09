from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.businesses.models import Business
from apps.products.models import Product

from .models import Sale
from .serializers import SaleCreateSerializer, SaleSerializer
from .services import VendaInvalida, cancelar_venda, intervalo_do_mes, registrar_venda, resumo_vendas


def _mes_pedido(request):
    """Le ?month=AAAA-MM; sem ele, o mes atual. Devolve (inicio, fim) ou None."""
    valor = request.query_params.get("month")
    if not valor:
        agora = timezone.localtime()
        return intervalo_do_mes(agora.year, agora.month)
    try:
        ano, mes = (int(parte) for parte in valor.split("-"))
        return intervalo_do_mes(ano, mes) if 1 <= mes <= 12 and 2000 <= ano <= 2100 else None
    except ValueError:
        return None


class SaleViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                  viewsets.GenericViewSet):
    """Vendas do negocio do usuario. Admin e member registram vendas.

    Sem update nem delete: uma venda errada e cancelada, o que devolve o
    estoque e tira a entrada do financeiro. Editar o passado deixaria o
    estoque e o lucro sem explicacao.
    """

    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]

    def _business(self):
        return Business.objects.filter(owner=self.request.user).first()

    def get_queryset(self):
        business = self._business()
        if not business:
            return Sale.objects.none()
        return Sale.objects.filter(business=business)

    def list(self, request, *args, **kwargs):
        intervalo = _mes_pedido(request)
        if intervalo is None:
            return Response({"detail": "Mês inválido. Use AAAA-MM."}, status=status.HTTP_400_BAD_REQUEST)
        inicio, fim = intervalo
        vendas = self.get_queryset().filter(occurred_at__gte=inicio, occurred_at__lt=fim)
        return Response(SaleSerializer(vendas, many=True).data)

    def create(self, request, *args, **kwargs):
        entrada = SaleCreateSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        dados = entrada.validated_data

        business = self._business()
        produto = Product.objects.filter(pk=dados["product_id"], business=business).first()
        if business is None or produto is None:
            return Response({"detail": "Produto não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        try:
            venda = registrar_venda(
                business=business,
                produto=produto,
                quantidade=dados["quantity"],
                payment_method=dados["payment_method"],
                preco_unitario=dados.get("unit_price"),
                occurred_at=dados.get("occurred_at"),
                user=request.user,
            )
        except VendaInvalida as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SaleSerializer(venda).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        venda = self.get_object()
        if venda.payment_id:
            return Response(
                {"detail": "Venda paga por PIX se desfaz pelo estorno da cobrança."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cancelar_venda(venda)
        return Response(SaleSerializer(venda).data)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Lucro realizado por produto no mes, para a visao geral."""
        intervalo = _mes_pedido(request)
        if intervalo is None:
            return Response({"detail": "Mês inválido. Use AAAA-MM."}, status=status.HTTP_400_BAD_REQUEST)
        business = self._business()
        if business is None:
            return Response({"totals": {}, "products": []})
        resumo = resumo_vendas(business, *intervalo)
        # Decimal vira string no JSON do DRF; aqui o resumo e montado a mao.
        def _json(item):
            return {chave: (str(valor) if hasattr(valor, "quantize") else valor) for chave, valor in item.items()}
        return Response({
            "totals": _json(resumo["totals"]),
            "products": [_json(item) for item in resumo["products"]],
        })
