from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import MarketingCampaignViewSet, marketing_chat

router = DefaultRouter()
router.register("campaigns", MarketingCampaignViewSet, basename="marketing-campaign")

urlpatterns = [
    path("chat/", marketing_chat, name="marketing-chat"),
    *router.urls,
]
