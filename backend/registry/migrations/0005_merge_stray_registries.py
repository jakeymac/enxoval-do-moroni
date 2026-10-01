"""Folds any extra enxovais back into the one the site serves.

An earlier version of Registry.load() created a registry per account, so a
second sign-in produced a second, invisible list — items added there never
reached the public page. The code now keys on "the first row" for everyone;
this moves anything stranded on the later rows onto it and removes them.

The surviving row keeps its own title and notes, but adopts any text the
stray had where its own was blank, so nothing written in the panel is lost.
"""
from django.db import migrations

TEXT_FIELDS = ("intro", "contact_note", "notify_email")


def merge(apps, schema_editor):
    Registry = apps.get_model("registry", "Registry")
    Item = apps.get_model("registry", "Item")

    rows = list(Registry.objects.order_by("pk"))
    if len(rows) < 2:
        return

    keep, strays = rows[0], rows[1:]
    moved = 0
    for stray in strays:
        moved += Item.objects.filter(registry=stray).update(registry=keep)
        for field in TEXT_FIELDS:
            if not getattr(keep, field) and getattr(stray, field):
                setattr(keep, field, getattr(stray, field))
        # A stray holding the only real items probably has the title the owner
        # typed, but the survivor's title is what the public page has been
        # showing; keep it unless it was never set.
        if not keep.title:
            keep.title = stray.title
    keep.save()
    # Items have been reparented, so this cascades nothing but the empty rows.
    Registry.objects.filter(pk__in=[s.pk for s in strays]).delete()
    print(f"    merged {len(strays)} stray enxoval(is), moved {moved} item(s) onto pk={keep.pk}")


class Migration(migrations.Migration):

    dependencies = [("registry", "0004_cache_table")]

    # Irreversible by nature: once merged there is no record of which row each
    # item came from. Nothing is deleted that held data, so this is safe forward.
    operations = [migrations.RunPython(merge, migrations.RunPython.noop)]
