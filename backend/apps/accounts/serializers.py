from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers
from rest_framework.authtoken.models import Token

from .models import UserProfile
from apps.businesses.models import Business

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    business_name = serializers.CharField(max_length=160, required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Este e-mail ja esta cadastrado.")
        return value.lower()

    def create(self, validated_data):
        email = validated_data["email"]
        user = User.objects.create_user(
            username=email,
            email=email,
            password=validated_data["password"],
            first_name=validated_data["name"],
        )
        admin_emails = [
            item.strip().lower()
            for item in getattr(settings, "WAGEUP_ADMIN_EMAILS", "").split(",")
            if item.strip()
        ]
        role = UserProfile.Role.ADMIN if email in admin_emails else UserProfile.Role.MEMBER
        biz_name = validated_data.get("business_name", "").strip() or validated_data["name"]
        UserProfile.objects.create(
            user=user,
            role=role,
            business_name=biz_name,
            onboarding_completed=bool(validated_data.get("business_name", "").strip()),
        )
        Business.objects.create(owner=user, name=biz_name)
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs["email"].lower()
        user = authenticate(username=email, password=attrs["password"])
        if not user:
            raise serializers.ValidationError("E-mail ou senha invalidos.")
        attrs["user"] = user
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    name = serializers.CharField(source="user.first_name", read_only=True)
    is_admin = serializers.SerializerMethodField()
    can_access_finance = serializers.BooleanField(read_only=True)
    can_manage_payments = serializers.BooleanField(read_only=True)
    # Taxa e imposto que o produto novo ja recebe preenchidos (Configuracoes).
    default_fee_percent = serializers.SerializerMethodField()
    default_tax_percent = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            "email",
            "name",
            "role",
            "business_name",
            "onboarding_completed",
            "is_admin",
            "can_access_finance",
            "can_manage_payments",
            "default_fee_percent",
            "default_tax_percent",
        ]

    def get_is_admin(self, obj):
        return obj.can_access_finance

    def _negocio(self, obj):
        cache = self.__dict__.setdefault("_negocios", {})
        if obj.user_id not in cache:
            cache[obj.user_id] = Business.objects.filter(owner=obj.user).first()
        return cache[obj.user_id]

    def get_default_fee_percent(self, obj):
        negocio = self._negocio(obj)
        return str(negocio.default_fee_percent) if negocio else "0.00"

    def get_default_tax_percent(self, obj):
        negocio = self._negocio(obj)
        return str(negocio.default_tax_percent) if negocio else "0.00"


class OnboardingSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["business_name", "onboarding_completed"]
        read_only_fields = ["onboarding_completed"]

    def update(self, instance, validated_data):
        instance.business_name = validated_data.get("business_name", instance.business_name)
        instance.onboarding_completed = True
        instance.save(update_fields=["business_name", "onboarding_completed", "updated_at"])
        # O perfil do negocio (Configuracoes) le o nome do Business: os dois
        # precisam dizer a mesma coisa.
        if instance.business_name:
            Business.objects.filter(owner=instance.user).update(name=instance.business_name)
        return instance


class PasswordResetRequestSerializer(serializers.Serializer):
    """Pedido de recuperacao. So valida o formato do e-mail.

    Nao checa se a conta existe de proposito: quem decide o que responder e a
    view, que responde igual nos dois casos.
    """

    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Troca a senha a partir do link enviado por e-mail.

    O token vem do `default_token_generator` do Django, que embute o hash da
    senha atual e o last_login. Isso faz o link expirar sozinho
    (PASSWORD_RESET_TIMEOUT) e deixar de valer assim que a senha muda, sem
    precisar de tabela de tokens no banco.
    """

    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(min_length=8, write_only=True)

    def validate(self, attrs):
        user = self._user_from_uid(attrs["uid"])
        # Mesma mensagem para uid corrompido, usuario inexistente, token
        # expirado ou ja usado: distinguir os casos entregaria a quem tem
        # conta na plataforma.
        if user is None or not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError(
                {"token": "Link inválido ou expirado. Peça um novo."}
            )
        try:
            validate_password(attrs["password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        attrs["user"] = user
        return attrs

    @staticmethod
    def _user_from_uid(uid):
        try:
            return User.objects.get(pk=urlsafe_base64_decode(uid).decode())
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return None

    def save(self):
        user = self.validated_data["user"]
        user.set_password(self.validated_data["password"])
        user.save(update_fields=["password"])
        # Sessao antiga nao sobrevive a troca de senha: quem redefine a senha
        # costuma estar justamente tentando expulsar quem nao deveria estar
        # dentro. Deixar o token velho valendo anularia o reset.
        Token.objects.filter(user=user).delete()
        return user
