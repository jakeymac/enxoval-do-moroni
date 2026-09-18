import logging

from django.core.mail import send_mail
from django.db import connections, transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Claim, Item, Registry
from .serializers import (
    ClaimCreateSerializer,
    ClaimSerializer,
    ItemSerializer,
    PublicRegistrySerializer,
    RegistrySerializer,
)

logger = logging.getLogger(__name__)


def healthz(request):
    """Liveness for the deploy script and the container healthcheck.

    Touches the database on purpose: a web process that answers while Postgres
    is unreachable is not healthy, and a deploy that rolls forward past that
    state is worse than one that fails loudly.
    """
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        logger.exception("Health check failed: database unreachable")
        return JsonResponse({"ok": False, "database": False}, status=503)
    return JsonResponse({"ok": True, "database": True})


def notify_owner(claim):
    """Avisa o dono do enxoval para que ele entre em contato com quem vai comprar."""
    registry = claim.item.registry
    to = registry.notify_email or registry.owner.email
    if not to:
        logger.warning(
            "Sem endereço de aviso para o enxoval %s; reserva %s não foi enviada por e-mail",
            registry.pk,
            claim.pk,
        )
        return
    body = (
        f"{claim.name} quer comprar um item de \"{registry.title}\".\n\n"
        f"Item:      {claim.item.name} (qtd {claim.quantity})\n"
        f"E-mail:    {claim.email}\n"
        f"Recado:    {claim.message or '(nenhum)'}\n\n"
        "Entre em contato para combinar os detalhes."
    )
    try:
        send_mail(
            subject=f"{claim.name} vai comprar: {claim.item.name}",
            message=body,
            from_email=None,
            recipient_list=[to],
            fail_silently=False,
        )
    except Exception:
        # Uma falha de e-mail nunca pode perder a reserva; ela fica salva e visível no painel.
        logger.exception("Falha ao enviar o aviso da reserva %s", claim.pk)


class PublicRegistryView(APIView):
    """GET /api/public/ — o enxoval, a página que todo mundo acessa."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        registry = Registry.load()
        if registry is None:
            raise Http404
        return Response(PublicRegistrySerializer(registry).data)


class PublicClaimView(APIView):
    """POST /api/public/items/<item_id>/claim/"""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "claim"

    def post(self, request, item_id):
        registry = Registry.load()
        if registry is None:
            raise Http404
        with transaction.atomic():
            # Trava a linha para que dois visitantes ao mesmo tempo não reservem além da conta.
            item = get_object_or_404(
                Item.objects.select_for_update().filter(registry=registry), pk=item_id
            )
            serializer = ClaimCreateSerializer(data=request.data, context={"item": item})
            serializer.is_valid(raise_exception=True)
            claim = serializer.save(item=item)

        notify_owner(claim)
        return Response(
            {
                "ok": True,
                "contact_note": registry.contact_note,
                "item": {"id": item.id, "quantity_remaining": item.quantity_remaining},
            },
            status=status.HTTP_201_CREATED,
        )


class RegistryView(RetrieveUpdateAPIView):
    """GET/PATCH /api/registry/ — o único enxoval da conta, criado no primeiro acesso."""

    serializer_class = RegistrySerializer

    def get_object(self):
        return Registry.load(owner=self.request.user)


class ItemViewSet(viewsets.ModelViewSet):
    serializer_class = ItemSerializer

    def get_queryset(self):
        return Item.objects.filter(registry__owner=self.request.user).prefetch_related("claims")


class ClaimViewSet(viewsets.ModelViewSet):
    """O dono vê quem reservou o quê e acompanha o contato. Reservas nunca nascem aqui."""

    serializer_class = ClaimSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return Claim.objects.filter(item__registry__owner=self.request.user).select_related("item")

    @action(detail=False, methods=["get"])
    def pending(self, request):
        qs = self.get_queryset().filter(status=Claim.Status.PENDING)
        return Response(self.get_serializer(qs, many=True).data)
