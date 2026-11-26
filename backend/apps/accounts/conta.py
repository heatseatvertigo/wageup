"""Perfil do negocio e configuracoes da conta.

O que o cartao da conta (na barra lateral) e a tela de Configuracoes leem e
gravam: dados da pessoa, senha, perfil do negocio, taxa e imposto padrao dos
produtos, o que esta ligado a plataforma e os direitos de exportar e apagar os
proprios dados (LGPD).

Isolamento: tudo parte de `request.user` e do negocio dele. Nenhuma rota recebe
id de usuario ou de negocio do cliente.
"""
import json
import re
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import F
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.businesses.models import Business
from apps.finance.goals import progresso_da_meta
from apps.finance.models import Goal, StatementImport, Transaction
from apps.payments.models import Payment
from apps.products.models import Product
from apps.sales.models import Sale
from apps.sales.services import intervalo_do_mes, resumo_vendas

from .serializers import UserProfileSerializer
from .throttles import PasswordCheckRateThrottle

User = get_user_model()

# Texto que a pessoa digita para confirmar que quer apagar a conta.
CONFIRMACAO_EXCLUSAO = "EXCLUIR"


def negocio_de(user):
    """O negocio da pessoa. Conta antiga sem negocio ganha um na hora."""
    negocio = Business.objects.filter(owner=user).first()
    if negocio is None:
        profile = getattr(user, "profile", None)
        nome = (profile.business_name if profile else "") or user.first_name or "Meu negócio"
        negocio = Business.objects.create(owner=user, name=nome)
    return negocio


def _dinheiro(valor):
    return str(Decimal(valor or 0).quantize(Decimal("0.01")))


# ─── Validacao de CNPJ ──────────────────────────────────────────────────────
# Desde julho de 2026 a Receita emite CNPJ alfanumerico: as 12 primeiras
# posicoes podem ter letras, e os 2 digitos verificadores continuam numericos.
# O calculo e o mesmo de sempre, com cada caractere valendo (codigo ASCII - 48),
# o que da o proprio digito para os numeros. Assim o CNPJ antigo e o novo
# passam pela mesma conta.

_PESOS_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_PESOS_2 = [6] + _PESOS_1


def _digito(base, pesos):
    soma = sum((ord(c) - 48) * p for c, p in zip(base, pesos))
    resto = soma % 11
    return "0" if resto < 2 else str(11 - resto)


def normalizar_cnpj(valor):
    """CNPJ formatado (XX.XXX.XXX/XXXX-XX), ou ValueError se for invalido."""
    limpo = re.sub(r"[^0-9A-Za-z]", "", valor or "").upper()
    if not limpo:
        return ""
    if not re.fullmatch(r"[0-9A-Z]{12}[0-9]{2}", limpo):
        raise ValueError("O CNPJ tem 14 caracteres: 12 letras ou números e 2 dígitos no fim.")
    if len(set(limpo)) == 1:
        raise ValueError("CNPJ inválido.")
    d1 = _digito(limpo[:12], _PESOS_1)
    d2 = _digito(limpo[:12] + d1, _PESOS_2)
    if limpo[12:] != d1 + d2:
        raise ValueError("CNPJ inválido: confira os dígitos.")
    return f"{limpo[:2]}.{limpo[2:5]}.{limpo[5:8]}/{limpo[8:12]}-{limpo[12:]}"


def normalizar_telefone(valor):
    """Telefone com DDD formatado, ou ValueError."""
    numeros = re.sub(r"\D", "", valor or "")
    if not numeros:
        return ""
    if numeros.startswith("55") and len(numeros) in (12, 13):
        numeros = numeros[2:]
    if len(numeros) not in (10, 11):
        raise ValueError("Informe o telefone com DDD, por exemplo (11) 91234-5678.")
    meio = 7 if len(numeros) == 11 else 6
    return f"({numeros[:2]}) {numeros[2:meio]}-{numeros[meio:]}"


# ─── Serializers ────────────────────────────────────────────────────────────

class NegocioSerializer(serializers.ModelSerializer):
    # So na escrita: aplica a taxa e o imposto padrao aos produtos ja cadastrados.
    apply_to_products = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = Business
        fields = [
            "name",
            "cnpj",
            "segment",
            "city",
            "phone",
            "default_fee_percent",
            "default_tax_percent",
            "apply_to_products",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Informe o nome do negócio.")
        return value

    def validate_cnpj(self, value):
        try:
            return normalizar_cnpj(value)
        except ValueError as erro:
            raise serializers.ValidationError(str(erro))

    def validate_phone(self, value):
        try:
            return normalizar_telefone(value)
        except ValueError as erro:
            raise serializers.ValidationError(str(erro))

    def validate_segment(self, value):
        return value.strip()

    def validate_city(self, value):
        return value.strip()

    def _percentual(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Use um percentual entre 0 e 100.")
        return value

    def validate_default_fee_percent(self, value):
        return self._percentual(value)

    def validate_default_tax_percent(self, value):
        return self._percentual(value)

    def validate(self, attrs):
        taxa = attrs.get("default_fee_percent", getattr(self.instance, "default_fee_percent", 0))
        imposto = attrs.get("default_tax_percent", getattr(self.instance, "default_tax_percent", 0))
        if (taxa or 0) + (imposto or 0) >= 100:
            raise serializers.ValidationError(
                {"default_tax_percent": "Taxa e imposto somados precisam ficar abaixo de 100%."}
            )
        return attrs

    def update(self, instance, validated_data):
        aplicar = validated_data.pop("apply_to_products", False)
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            # O nome tambem mora no perfil, que o app le no cabecalho.
            profile = getattr(instance.owner, "profile", None)
            if profile and profile.business_name != instance.name:
                profile.business_name = instance.name
                profile.save(update_fields=["business_name", "updated_at"])
            self.produtos_atualizados = 0
            if aplicar:
                self.produtos_atualizados = Product.objects.filter(business=instance).update(
                    fee_percent=instance.default_fee_percent,
                    tax_percent=instance.default_tax_percent,
                )
        return instance


class ContaSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    email = serializers.EmailField(required=False)
    current_password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Informe seu nome.")
        return value

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("Este e-mail já está em uso.")
        return value

    def validate(self, attrs):
        user = self.instance
        novo = attrs.get("email")
        # O e-mail e o login: trocar pede a senha atual, para quem achar o
        # computador aberto nao tomar a conta.
        if novo and novo != (user.email or "").lower():
            if not user.check_password(attrs.get("current_password") or ""):
                raise serializers.ValidationError({"current_password": "Senha atual incorreta."})
        return attrs

    def update(self, user, validated_data):
        campos = []
        if "name" in validated_data:
            user.first_name = validated_data["name"]
            campos.append("first_name")
        novo = validated_data.get("email")
        if novo and novo != (user.email or "").lower():
            user.email = novo
            user.username = novo
            campos += ["email", "username"]
        if campos:
            user.save(update_fields=campos)
        return user


class TrocaDeSenhaSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        user = self.context["user"]
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError({"current_password": "Senha atual incorreta."})
        try:
            validate_password(attrs["new_password"], user)
        except DjangoValidationError as erro:
            raise serializers.ValidationError({"new_password": list(erro.messages)})
        return attrs


# ─── Rotas ──────────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def perfil_view(request):
    """Resumo do perfil: pessoa, negocio, numeros do mes e principais produtos.

    Os numeros vem das vendas, que admin e membro veem. Meta e PIX leem o
    financeiro e so vao para o admin.
    """
    user = request.user
    profile = user.profile
    negocio = negocio_de(user)
    hoje = timezone.localdate()
    inicio, fim = intervalo_do_mes(hoje.year, hoje.month)
    resumo = resumo_vendas(negocio, inicio, fim)
    vendidos = {item["product_id"]: item for item in resumo["products"] if item["product_id"]}

    produtos = Product.objects.filter(business=negocio)
    ativos = produtos.filter(is_active=True)
    # Abaixo do minimo ou zerado; servico nao tem estoque.
    estoque_baixo = ativos.exclude(unit=Product.Unit.SERVICE).filter(stock__lte=F("min_stock")).count()

    def chave(produto):
        item = vendidos.get(str(produto.id))
        return (-(item["profit"] if item else Decimal("-1E9")), produto.name.lower())

    principais = []
    for produto in sorted(ativos, key=chave)[:6]:
        item = vendidos.get(str(produto.id))
        principais.append({
            "id": str(produto.id),
            "name": produto.name,
            "category": produto.category,
            "unit": produto.unit,
            "price": _dinheiro(produto.price),
            "margin_percent": str(produto.margin_percent),
            "stock": produto.stock,
            "min_stock": produto.min_stock,
            "controls_stock": produto.unit != Product.Unit.SERVICE,
            "sold_month": item["quantity"] if item else 0,
            "profit_month": _dinheiro(item["profit"] if item else 0),
        })

    totais = resumo["totals"]
    dados = {
        "user": {
            "name": user.first_name or user.email,
            "email": user.email,
            "role": profile.role,
            "role_label": "Admin" if profile.can_access_finance else "Membro",
            "member_since": timezone.localtime(user.date_joined).date().isoformat(),
        },
        "business": NegocioSerializer(negocio).data,
        "month": f"{hoje.year:04d}-{hoje.month:02d}",
        "stats": {
            "sales_count": totais["count"],
            "units": totais["quantity"],
            "revenue": _dinheiro(totais["total"]),
            "profit": _dinheiro(totais["profit"]),
            "products_active": ativos.count(),
            "products_total": produtos.count(),
            "low_stock": estoque_baixo,
        },
        "products": principais,
        "goal": None,
        "pix_pending": None,
    }
    if profile.can_access_finance:
        dados["goal"] = progresso_da_meta(negocio, hoje.year, hoje.month)
        pendentes = Payment.objects.filter(business=negocio, status=Payment.Status.PENDING)
        dados["pix_pending"] = {
            "count": pendentes.count(),
            "amount": _dinheiro(sum((p.amount for p in pendentes), Decimal("0"))),
        }
    return Response(dados)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
@throttle_classes([PasswordCheckRateThrottle])
def conta_view(request):
    """PATCH troca nome e e-mail; DELETE apaga a conta e tudo do negocio."""
    user = request.user
    if request.method == "PATCH":
        serializer = ContaSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserProfileSerializer(user.profile).data)

    if not user.check_password(request.data.get("password") or ""):
        return Response({"password": ["Senha incorreta."]}, status=status.HTTP_400_BAD_REQUEST)
    if (request.data.get("confirm") or "").strip().upper() != CONFIRMACAO_EXCLUSAO:
        return Response(
            {"confirm": [f"Digite {CONFIRMACAO_EXCLUSAO} para confirmar."]},
            status=status.HTTP_400_BAD_REQUEST,
        )
    with transaction.atomic():
        # O negocio leva junto produtos, vendas, financeiro, PIX e campanhas.
        Business.objects.filter(owner=user).delete()
        user.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([PasswordCheckRateThrottle])
def senha_view(request):
    """Troca a senha. Os outros acessos abertos saem: o token muda."""
    serializer = TrocaDeSenhaSerializer(data=request.data, context={"user": request.user})
    serializer.is_valid(raise_exception=True)
    user = request.user
    user.set_password(serializer.validated_data["new_password"])
    user.save(update_fields=["password"])
    Token.objects.filter(user=user).delete()
    token = Token.objects.create(user=user)
    return Response({"token": token.key, "detail": "Senha alterada."})


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def negocio_view(request):
    """Perfil do negocio e os padroes de taxa e imposto dos produtos."""
    negocio = negocio_de(request.user)
    if request.method == "GET":
        return Response(NegocioSerializer(negocio).data)
    serializer = NegocioSerializer(negocio, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    dados = dict(serializer.data)
    dados["products_updated"] = getattr(serializer, "produtos_atualizados", 0)
    return Response(dados)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def conexoes_view(request):
    """O que esta ligado a plataforma, sem expor chave nenhuma.

    PIX e extrato sao do financeiro e so aparecem para o admin.
    """
    negocio = negocio_de(request.user)
    admin = request.user.profile.can_access_finance
    itens = []

    if admin:
        itens.append({
            "key": "pix",
            "name": "PIX",
            "provider": "Abacate Pay",
            "status": "active" if settings.ABACATE_PAY_API_KEY else "off",
            "detail": (
                "Cobranças com QR Code e baixa automática quando o cliente paga."
                if settings.ABACATE_PAY_API_KEY
                else "Sem chave da Abacate Pay: a plataforma não gera cobranças."
            ),
        })
        ultimo = StatementImport.objects.filter(business=negocio).first()
        itens.append({
            "key": "statement",
            "name": "Extrato bancário",
            "provider": "Arquivo OFX do seu banco",
            "status": "active" if ultimo else "available",
            "detail": (
                f"Última importação em {timezone.localtime(ultimo.created_at):%d/%m/%Y}, "
                f"com {ultimo.imported_count} lançamentos."
                if ultimo
                else "Nenhum extrato importado ainda. Importe em Movimentações."
            ),
        })

    if settings.DEEPSEEK_API_KEY or settings.ANTHROPIC_API_KEY:
        provedor = "DeepSeek" if settings.DEEPSEEK_API_KEY else "Anthropic"
        itens.append({
            "key": "ai", "name": "Inteligência artificial", "provider": provedor, "status": "active",
            "detail": "Assistente financeiro, insights e campanhas de marketing.",
        })
    else:
        itens.append({
            "key": "ai", "name": "Inteligência artificial", "provider": "Regras locais", "status": "off",
            "detail": "Sem IA configurada: as respostas vêm de regras da própria plataforma.",
        })

    if settings.CLOUDFLARE_ACCOUNT_ID and settings.CLOUDFLARE_API_TOKEN:
        imagem = ("Cloudflare Workers AI", "active", "Imagem de cada campanha gerada pelo marketing.")
    elif settings.MARKETING_IMAGE_FALLBACK:
        imagem = ("Pollinations.ai", "active", "Imagem das campanhas por um serviço gratuito, com marca d'água.")
    else:
        imagem = ("Nenhum", "off", "As campanhas saem só com texto.")
    itens.append({"key": "images", "name": "Imagens de campanha", "provider": imagem[0], "status": imagem[1], "detail": imagem[2]})

    itens.append({
        "key": "google",
        "name": "Entrar com Google",
        "provider": "Google",
        "status": "available" if settings.GOOGLE_CLIENT_ID else "off",
        "detail": (
            "Você pode entrar com a conta Google do mesmo e-mail."
            if settings.GOOGLE_CLIENT_ID
            else "Login com Google não está ativo nesta instalação."
        ),
    })
    if admin:
        itens.append({
            "key": "bank",
            "name": "Conta bancária conectada",
            "provider": "Open Finance",
            "status": "soon",
            "detail": "Lançamentos do banco entrando sozinhos. Por enquanto, importe o extrato.",
        })
    return Response({"items": itens})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def exportar_view(request):
    """Tudo o que a conta guarda, num arquivo JSON (direito de acesso da LGPD).

    O membro nao ve o financeiro na plataforma, entao o arquivo dele tambem nao
    traz lancamentos, PIX nem meta.
    """
    user = request.user
    negocio = negocio_de(user)
    admin = user.profile.can_access_finance
    dados = {
        "generated_at": timezone.now(),
        "account": {
            "name": user.first_name,
            "email": user.email,
            "role": user.profile.role,
            "member_since": user.date_joined,
        },
        "business": NegocioSerializer(negocio).data,
        "products": list(Product.objects.filter(business=negocio).values(
            "id", "name", "sku", "category", "description", "unit", "price", "cost", "other_costs",
            "fee_percent", "tax_percent", "stock", "min_stock", "is_active", "created_at",
        )),
        "sales": list(Sale.objects.filter(business=negocio).values(
            "id", "product_name", "quantity", "unit_price", "unit_cost", "fee_percent", "tax_percent",
            "total", "cost_total", "fees", "profit", "payment_method", "status", "occurred_at", "canceled_at",
        )),
    }
    if admin:
        dados["transactions"] = list(Transaction.objects.filter(business=negocio).values(
            "id", "description", "type", "amount", "source", "payment_method", "occurred_at",
        ))
        dados["pix_charges"] = list(Payment.objects.filter(business=negocio).values(
            "id", "amount", "status", "created_at",
        ))
        dados["goals"] = list(Goal.objects.filter(business=negocio).values("month", "target_amount"))

    conteudo = json.dumps(dados, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2)
    resposta = HttpResponse(conteudo, content_type="application/json; charset=utf-8")
    nome = f"wageup-meus-dados-{timezone.localdate():%Y-%m-%d}.json"
    resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    return resposta
