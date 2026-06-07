from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers

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
        ]

    def get_is_admin(self, obj):
        return obj.can_access_finance


class OnboardingSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["business_name", "onboarding_completed"]
        read_only_fields = ["onboarding_completed"]

    def update(self, instance, validated_data):
        instance.business_name = validated_data.get("business_name", instance.business_name)
        instance.onboarding_completed = True
        instance.save(update_fields=["business_name", "onboarding_completed", "updated_at"])
        return instance
