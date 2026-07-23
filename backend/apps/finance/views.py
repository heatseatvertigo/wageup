from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminRole
from apps.businesses.models import Business
from .insights import build_insights
from .models import Transaction
from .serializers import TransactionSerializer


class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Transaction.objects.all()
        business = Business.objects.filter(owner=self.request.user).first()
        if not business:
            return Transaction.objects.none()
        return Transaction.objects.filter(business=business)

    def perform_create(self, serializer):
        business = Business.objects.filter(owner=self.request.user).first()
        serializer.save(business=business)


@api_view(["GET"])
@permission_classes([IsAdminRole])
def business_insights(request):
    """Insights de negócio gerados por IA (com fallback local) para o dashboard."""
    business = Business.objects.filter(owner=request.user).first()
    if not business:
        return Response({"provider": "local-demo", "insights": []})
    provider, insights = build_insights(business)
    return Response({"provider": provider, "insights": insights})
