import hashlib

from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.businesses.models import Business
from .models import Product, ProductImage
from .serializers import ProductSerializer


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        business = Business.objects.filter(owner=self.request.user).first()
        if not business:
            return Product.objects.none()
        # select_related evita uma consulta por produto so para saber se ha foto.
        return Product.objects.filter(business=business).select_related("image")

    def perform_create(self, serializer):
        business = Business.objects.filter(owner=self.request.user).first()
        serializer.save(business=business)

    @action(detail=True, methods=["get", "post", "delete"], url_path="image")
    def image(self, request, pk=None):
        """Le, grava e remove a foto do produto.

        A foto vive no banco, nao em disco: o disco do Render some a cada
        deploy. A rota exige autenticacao como qualquer outra, entao a tela
        busca a imagem com o token e monta um object URL, em vez de apontar o
        <img> direto para ca.
        """
        produto = self.get_object()

        if request.method == "GET":
            return self._devolver_imagem(request, produto)
        if request.method == "DELETE":
            ProductImage.objects.filter(product=produto).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return self._gravar_imagem(request, produto)

    @staticmethod
    def _devolver_imagem(request, produto):
        imagem = getattr(produto, "image", None)
        if imagem is None:
            return Response({"detail": "Este produto nao tem foto."}, status=status.HTTP_404_NOT_FOUND)

        etag = f'"{imagem.checksum}"'
        if request.headers.get("If-None-Match") == etag:
            return HttpResponse(status=status.HTTP_304_NOT_MODIFIED)

        resposta = HttpResponse(bytes(imagem.data), content_type=imagem.content_type)
        resposta["ETag"] = etag
        # A foto so muda quando o usuario troca, e a troca muda o ETag.
        resposta["Cache-Control"] = "private, max-age=86400"
        return resposta

    @staticmethod
    def _gravar_imagem(request, produto):
        enviado = request.FILES.get("file")
        if not enviado:
            return Response({"detail": "Envie a foto no campo 'file'."}, status=status.HTTP_400_BAD_REQUEST)

        if enviado.content_type not in ProductImage.CONTENT_TYPES:
            aceitos = ", ".join(tipo.split("/")[1].upper() for tipo in ProductImage.CONTENT_TYPES)
            return Response(
                {"detail": f"Formato nao aceito. Use {aceitos}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        conteudo = enviado.read()
        if len(conteudo) > ProductImage.MAX_BYTES:
            limite = ProductImage.MAX_BYTES // 1024
            return Response(
                {"detail": f"Foto grande demais. O limite e {limite} KB depois da reducao."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        ProductImage.objects.update_or_create(
            product=produto,
            defaults={
                "content_type": enviado.content_type,
                "data": conteudo,
                "checksum": hashlib.sha256(conteudo).hexdigest(),
            },
        )
        return Response(ProductSerializer(produto).data, status=status.HTTP_201_CREATED)
