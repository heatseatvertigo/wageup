from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import MarketingCampaignViewSet, marketing_chat, marketing_recommendations

router = DefaultRouter()
router.register("campaigns", MarketingCampaignViewSet, basename="marketing-campaign")

urlpatterns = [
    path("chat/", marketing_chat, name="marketing-chat"),
    path("recommendations/", marketing_recommendations, name="marketing-recommendations"),
    *router.urls,
]
