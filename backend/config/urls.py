"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve
from django.conf import settings

from apps.finance.views import (
    assistant_conversation_detail,
    assistant_conversations,
    business_insights,
    finance_assistant,
)
from .views import frontend_index, health_check

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health_check, name='health-check'),
    path('api/auth/', include('apps.accounts.urls')),
    path('api/products/', include('apps.products.urls')),
    path('api/transactions/', include('apps.finance.urls')),
    path('api/finance/insights/', business_insights, name='business-insights'),
    path('api/finance/assistant/', finance_assistant, name='finance-assistant'),
    path('api/finance/assistant/conversations/', assistant_conversations, name='assistant-conversations'),
    path('api/finance/assistant/conversations/<uuid:conversation_id>/', assistant_conversation_detail, name='assistant-conversation-detail'),
    path('api/payments/', include('apps.payments.urls')),
    path('api/marketing/', include('apps.marketing.urls')),
    path('api/sales/', include('apps.sales.urls')),
    re_path(r'^(?P<path>app\.js|styles\.css)$', serve, {'document_root': settings.ROOT_DIR / 'frontend'}),
    path('', frontend_index, name='frontend-index'),
]
