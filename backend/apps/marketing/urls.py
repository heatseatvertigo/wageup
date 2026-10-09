from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    MarketingCampaignViewSet,
    campaign_image,
    marketing_action,
    marketing_chat,
    marketing_products,
    marketing_conversation_detail,
    marketing_conversations,
    marketing_recommendations,
)

router = DefaultRouter()
router.register("campaigns", MarketingCampaignViewSet, basename="marketing-campaign")

urlpatterns = [
    path("chat/", marketing_chat, name="marketing-chat"),
    path("conversations/", marketing_conversations, name="marketing-conversations"),
    path(
        "conversations/<uuid:conversation_id>/",
        marketing_conversation_detail,
        name="marketing-conversation-detail",
    ),
    path("recommendations/", marketing_recommendations, name="marketing-recommendations"),
    path("actions/", marketing_action, name="marketing-action"),
    path("products/", marketing_products, name="marketing-products"),
    path("campaigns/<uuid:campaign_id>/image/", campaign_image, name="marketing-campaign-image"),
    *router.urls,
]
