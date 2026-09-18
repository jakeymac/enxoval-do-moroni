from django.contrib import admin

from .models import Claim, Item, Registry

admin.site.site_header = "Enxoval"
admin.site.site_title = "Enxoval"
admin.site.index_title = "Administração"


class ItemInline(admin.TabularInline):
    model = Item
    extra = 1


@admin.register(Registry)
class RegistryAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "is_published", "created_at")
    inlines = [ItemInline]


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "quantity_needed", "quantity_claimed", "quantity_remaining")


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "item", "quantity", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("first_name", "last_name", "email")

    @admin.display(description="quem reservou")
    def name(self, obj):
        return obj.name
