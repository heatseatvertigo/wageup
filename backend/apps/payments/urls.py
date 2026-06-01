from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import PaymentViewSet, abacatepay_webhook

router = DefaultRouter()
router.register("", PaymentViewSet, basename="payment")

urlpatterns = [
    path("webhooks/abacatepay/", abacatepay_webhook, name="abacatepay-webhook"),
    *router.urls,
]
