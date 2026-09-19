import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.businesses.models import Business
from .emails import send_password_reset_email
from .models import UserProfile
from .serializers import (
    LoginSerializer,
    OnboardingSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserProfileSerializer,
)
from .throttles import LoginRateThrottle

User = get_user_model()
logger = logging.getLogger(__name__)


def auth_payload(user):
    token, _ = Token.objects.get_or_create(user=user)
    profile = getattr(user, "profile", None)
    return {
        "token": token.key,
        "user": UserProfileSerializer(profile).data,
    }


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def register_view(request):
    """Cria conta. Limitado para evitar criacao de contas em massa."""
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    return Response(auth_payload(user), status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def login_view(request):
    """Autentica. Limitado para dificultar tentativa de senha por forca bruta."""
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(auth_payload(serializer.validated_data["user"]))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    Token.objects.filter(user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    return Response(UserProfileSerializer(request.user.profile).data)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def onboarding_view(request):
    serializer = OnboardingSerializer(request.user.profile, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(UserProfileSerializer(request.user.profile).data)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def google_signin_view(request):
    if not settings.GOOGLE_CLIENT_ID:
        return Response({"detail": "Google login não configurado."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    credential = request.data.get("credential", "")
    if not credential:
        return Response({"detail": "credential obrigatório."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token
        idinfo = google_id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except Exception:
        return Response({"detail": "Token Google inválido."}, status=status.HTTP_401_UNAUTHORIZED)

    email = idinfo.get("email", "").lower()
    name = idinfo.get("name", "") or idinfo.get("given_name", "") or email.split("@")[0]

    if not email:
        return Response({"detail": "E-mail não disponível na conta Google."}, status=status.HTTP_400_BAD_REQUEST)

    user, created = User.objects.get_or_create(
        email=email,
        defaults={"username": email, "first_name": name},
    )

    if created:
        admin_emails = [
            item.strip().lower()
            for item in getattr(settings, "WAGEUP_ADMIN_EMAILS", "").split(",")
            if item.strip()
        ]
        role = UserProfile.Role.ADMIN if email in admin_emails else UserProfile.Role.MEMBER
        UserProfile.objects.create(user=user, role=role, business_name=name)
        Business.objects.create(owner=user, name=name)
    elif not hasattr(user, "profile"):
        UserProfile.objects.create(user=user, role=UserProfile.Role.MEMBER, business_name=name)
        Business.objects.filter(owner=user).get_or_create(defaults={"name": name})

    return Response(auth_payload(user), status=status.HTTP_200_OK)


# Resposta unica do pedido de recuperacao, existindo a conta ou nao.
PASSWORD_RESET_SENT_DETAIL = (
    "Se existir uma conta com este e-mail, enviamos um link de recuperação."
)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def password_reset_request_view(request):
    """Envia o link de recuperacao por e-mail.

    Responde o mesmo texto havendo conta ou nao: um 404 para e-mail
    desconhecido transformaria a rota num verificador de quem tem conta na
    plataforma. Falha no envio tambem nao muda a resposta — vai para o log,
    porque o erro e nosso e nao diz nada ao visitante.
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = User.objects.filter(email__iexact=serializer.validated_data["email"]).first()
    if user is not None:
        try:
            send_password_reset_email(user, request)
        except Exception:
            logger.exception("Falha ao enviar e-mail de recuperacao de senha")

    return Response({"detail": PASSWORD_RESET_SENT_DETAIL})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def password_reset_confirm_view(request):
    """Grava a senha nova a partir do uid e do token do link.

    Nao devolve token de autenticacao: depois de trocar a senha o usuario
    entra de novo pela tela de login, o que confirma que a senha nova e a que
    ele acredita ter escolhido.
    """
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response({"detail": "Senha alterada. Entre com a senha nova."})
