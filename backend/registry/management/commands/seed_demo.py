"""Cria a conta do dono e um enxoval de exemplo, para poder clicar no app na hora."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from registry.models import Item, Registry

SAMPLE_ITEMS = [
    ("Jogo de lençóis de casal", "Dois jogos, cores neutras", 2, 250),
    ("Jogo de panelas", "Antiaderente, pode ir ao forno", 1, 650),
    ("Filtro de água", "Para a água de beber na casa do campo missionário", 1, 320),
    ("Jogo de toalhas de banho", "", 3, 140),
    ("Bateria portátil", "Para as viagens entre as comunidades", 1, 220),
]


class Command(BaseCommand):
    help = "Cria uma conta de demonstração e um enxoval de exemplo."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="owner")
        parser.add_argument("--password", default="registry123")
        parser.add_argument("--email", default="owner@example.com")

    def handle(self, *args, **opts):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=opts["username"], defaults={"email": opts["email"], "is_staff": True}
        )
        if created:
            user.set_password(opts["password"])
            user.save()
            self.stdout.write(f"Conta criada: {user.username} / {opts['password']}")

        registry = Registry.load(owner=user)
        if not registry.items.exists():
            registry.title = "Enxoval Missionário"
            registry.intro = (
                "Obrigado por nos ajudar a montar a casa no campo missionário! "
                "Escolha um item abaixo e entraremos em contato para combinar os detalhes."
            )
            registry.contact_note = (
                "Vamos te escrever nos próximos dias para agradecer e combinar os detalhes."
            )
            registry.save()
            for position, (name, desc, qty, price) in enumerate(SAMPLE_ITEMS):
                Item.objects.create(
                    registry=registry,
                    name=name,
                    description=desc,
                    quantity_needed=qty,
                    estimated_price=price,
                    position=position,
                )
        self.stdout.write(self.style.SUCCESS("Enxoval pronto. A página pública é a raiz do site: /"))
