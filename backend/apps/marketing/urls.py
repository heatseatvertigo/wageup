from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    MarketingCampaignViewSet,
    campaign_image,
    marketing_chat,
    marketing_recommendations,
)

router = DefaultRouter()
router.register("campaigns", MarketingCampaignViewSet, basename="marketing-campaign")

urlpatterns = [
    path("chat/", marketing_chat, name="marketing-chat"),
    path("recommendations/", marketing_recommendations, name="marketing-recommendations"),
    path("campaigns/<uuid:campaign_id>/image/", campaign_image, name="marketing-campaign-image"),
    *router.urls,
]
