from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    ClaimViewSet,
    ItemViewSet,
    PublicClaimView,
    PublicRegistryView,
    RegistryView,
)

router = DefaultRouter()
router.register("items", ItemViewSet, basename="item")
router.register("claims", ClaimViewSet, basename="claim")

urlpatterns = [
    path("auth/login/", TokenObtainPairView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("public/", PublicRegistryView.as_view(), name="public-registry"),
    path("public/items/<int:item_id>/claim/", PublicClaimView.as_view(), name="public-claim"),
    path("registry/", RegistryView.as_view(), name="registry"),
    path("", include(router.urls)),
]
