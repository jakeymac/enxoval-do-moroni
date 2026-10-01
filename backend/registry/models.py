from django.conf import settings
from django.db import models
from django.db.models import Sum


class Registry(models.Model):
    """The enxoval. There is one, served at the site root.

    Kept as a row rather than settings so the owner can edit the title, intro and
    thank-you note from the admin area without a deploy.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="registries"
    )
    title = models.CharField("título", max_length=140)
    intro = models.TextField(
        "introdução",
        blank=True,
        help_text="Aparece no topo da página pública. Para quem é o enxoval e por quê.",
    )
    contact_note = models.CharField(
        "mensagem de agradecimento",
        max_length=240,
        blank=True,
        help_text="Aparece depois que alguém reserva um item, ex.: 'Entraremos em contato esta semana.'",
    )
    notify_email = models.EmailField(
        "e-mail para avisos",
        blank=True,
        help_text="Para onde vão os avisos de reserva. Sem isso, usa o e-mail da conta.",
    )
    is_published = models.BooleanField("publicado", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "enxoval"
        verbose_name_plural = "enxovais"
        ordering = ["pk"]

    def __str__(self):
        return self.title

    @classmethod
    def load(cls, owner=None):
        """The enxoval. There is one, and every account manages that same one.

        Keyed on nothing but "the first row": an earlier version looked it up per
        owner and created a fresh enxoval for any account that did not have one,
        so a second account silently got a second, invisible list — items added
        there never appeared on the public page. One household, one enxoval; who
        happens to be signed in does not change which list they are editing.

        `owner` is only the fallback for a brand new install with no rows yet.
        Passing it also means "this is the owner side", which skips the
        is_published check so the panel still works while the page is offline.
        """
        registry = cls.objects.order_by("pk").first()
        if registry is None:
            if owner is None:
                return None
            return cls.objects.create(owner=owner, title="Nosso Enxoval")
        if owner is None and not registry.is_published:
            return None
        return registry


class Item(models.Model):
    registry = models.ForeignKey(Registry, on_delete=models.CASCADE, related_name="items")
    name = models.CharField("item", max_length=160)
    description = models.TextField("descrição", blank=True)
    quantity_needed = models.PositiveIntegerField("quantidade necessária", default=1)
    estimated_price = models.DecimalField(
        "preço estimado", max_digits=9, decimal_places=2, null=True, blank=True
    )
    product_url = models.URLField(
        "link do produto", blank=True, help_text="Onde comprar, se houver um bom link."
    )
    image_url = models.URLField("link da foto", blank=True)
    position = models.PositiveIntegerField("posição", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "item"
        verbose_name_plural = "itens"
        ordering = ["position", "created_at"]

    def __str__(self):
        return self.name

    @property
    def quantity_claimed(self):
        """Reservas canceladas liberam o item de novo."""
        agg = self.claims.exclude(status=Claim.Status.CANCELLED).aggregate(n=Sum("quantity"))
        return agg["n"] or 0

    @property
    def quantity_remaining(self):
        return max(self.quantity_needed - self.quantity_claimed, 0)

    @property
    def is_fully_claimed(self):
        return self.quantity_remaining == 0


class Claim(models.Model):
    """Alguém dizendo 'vou comprar este'. O dono entra em contato a partir daqui."""

    class Status(models.TextChoices):
        PENDING = "pending", "Aguardando contato"
        CONTACTED = "contacted", "Contato feito"
        FULFILLED = "fulfilled", "Recebido"
        CANCELLED = "cancelled", "Cancelado"

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="claims")
    first_name = models.CharField("nome", max_length=80)
    last_name = models.CharField("sobrenome", max_length=80)
    email = models.EmailField("e-mail")
    message = models.TextField("recado", blank=True)
    quantity = models.PositiveIntegerField("quantidade", default=1)
    status = models.CharField(
        "situação", max_length=12, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "reserva"
        verbose_name_plural = "reservas"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} -> {self.item}"

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}".strip()
