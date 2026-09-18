from rest_framework import serializers

from .models import Claim, Item, Registry


class PublicItemSerializer(serializers.ModelSerializer):
    """O que os visitantes veem. Esconde de propósito quem reservou o quê."""

    quantity_remaining = serializers.IntegerField(read_only=True)
    is_fully_claimed = serializers.BooleanField(read_only=True)

    class Meta:
        model = Item
        fields = [
            "id",
            "name",
            "description",
            "quantity_needed",
            "quantity_remaining",
            "is_fully_claimed",
            "estimated_price",
            "product_url",
            "image_url",
        ]


class PublicRegistrySerializer(serializers.ModelSerializer):
    items = PublicItemSerializer(many=True, read_only=True)

    class Meta:
        model = Registry
        fields = ["title", "intro", "contact_note", "items"]


class ClaimCreateSerializer(serializers.ModelSerializer):
    """Nome, sobrenome e e-mail são obrigatórios: é como o dono responde depois."""

    class Meta:
        model = Claim
        fields = ["id", "first_name", "last_name", "email", "message", "quantity"]
        extra_kwargs = {
            "first_name": {
                "required": True,
                "allow_blank": False,
                "error_messages": {
                    "required": "Preencha seu nome no topo da página.",
                    "blank": "Preencha seu nome no topo da página.",
                },
            },
            "last_name": {
                "required": True,
                "allow_blank": False,
                "error_messages": {
                    "required": "Preencha seu sobrenome no topo da página.",
                    "blank": "Preencha seu sobrenome no topo da página.",
                },
            },
            "email": {
                "required": True,
                "allow_blank": False,
                "error_messages": {
                    "required": "Preencha seu e-mail no topo da página.",
                    "blank": "Preencha seu e-mail no topo da página.",
                    "invalid": "Esse e-mail não parece válido.",
                },
            },
        }

    def validate(self, attrs):
        item = self.context["item"]
        quantity = attrs.get("quantity", 1)
        if quantity < 1:
            raise serializers.ValidationError({"quantity": "Precisa ser pelo menos 1."})
        if quantity > item.quantity_remaining:
            raise serializers.ValidationError(
                {"quantity": f"Faltam apenas {item.quantity_remaining} deste item."}
            )
        return attrs


class ClaimSerializer(serializers.ModelSerializer):
    """Visão do dono: quem reservou o quê, e em que pé está o contato."""

    name = serializers.CharField(read_only=True)
    item_name = serializers.CharField(source="item.name", read_only=True)

    class Meta:
        model = Claim
        fields = [
            "id",
            "item",
            "item_name",
            "name",
            "first_name",
            "last_name",
            "email",
            "message",
            "quantity",
            "status",
            "created_at",
        ]
        read_only_fields = [
            "item",
            "first_name",
            "last_name",
            "email",
            "message",
            "quantity",
            "created_at",
        ]


class ItemSerializer(serializers.ModelSerializer):
    """Visão do dono: inclui a contagem de reservas."""

    quantity_claimed = serializers.IntegerField(read_only=True)
    quantity_remaining = serializers.IntegerField(read_only=True)
    claims = ClaimSerializer(many=True, read_only=True)

    class Meta:
        model = Item
        fields = [
            "id",
            "registry",
            "name",
            "description",
            "quantity_needed",
            "quantity_claimed",
            "quantity_remaining",
            "estimated_price",
            "product_url",
            "image_url",
            "position",
            "claims",
        ]

    def validate_registry(self, registry):
        if registry.owner_id != self.context["request"].user.id:
            raise serializers.ValidationError("Este enxoval não é seu.")
        return registry


class RegistrySerializer(serializers.ModelSerializer):
    items = ItemSerializer(many=True, read_only=True)
    pending_claims = serializers.SerializerMethodField()

    class Meta:
        model = Registry
        fields = [
            "id",
            "title",
            "intro",
            "contact_note",
            "notify_email",
            "is_published",
            "items",
            "pending_claims",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def get_pending_claims(self, obj):
        return Claim.objects.filter(item__registry=obj, status=Claim.Status.PENDING).count()
