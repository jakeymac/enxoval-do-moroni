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
        """The one enxoval. Created on first use so a fresh account is never empty.

        Without an owner this is the public lookup, and it is deliberately pinned
        to the first enxoval ever created: if a second account exists, taking the
        real one off the air must take the page down, not quietly promote someone
        else's list to the site root.
        """
        if owner is not None:
            registry = cls.objects.filter(owner=owner).order_by("pk").first()
            return registry or cls.objects.create(owner=owner, title="Nosso Enxoval")
        registry = cls.objects.order_by("pk").first()
        return registry if registry and registry.is_published else None


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
