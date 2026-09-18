"""Claims now collect a first name, a last name and a required e-mail.

Splits any existing `name` into the two halves rather than dropping it, and
folds a phone number — a field the public form no longer offers — into the
message so no way of reaching a giver is lost.
"""
from django.db import migrations, models


def split_names(apps, schema_editor):
    Claim = apps.get_model("registry", "Claim")
    for claim in Claim.objects.all().iterator():
        first, _, last = (claim.name or "").strip().partition(" ")
        claim.first_name = first
        claim.last_name = last.strip()
        if claim.phone:
            note = f"Telefone: {claim.phone}"
            claim.message = f"{claim.message}\n{note}".strip() if claim.message else note
        claim.save(update_fields=["first_name", "last_name", "message"])


def rejoin_names(apps, schema_editor):
    Claim = apps.get_model("registry", "Claim")
    for claim in Claim.objects.all().iterator():
        claim.name = f"{claim.first_name} {claim.last_name}".strip()
        claim.save(update_fields=["name"])


class Migration(migrations.Migration):

    dependencies = [("registry", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="claim",
            name="first_name",
            field=models.CharField(default="", max_length=80, verbose_name="nome"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="claim",
            name="last_name",
            field=models.CharField(default="", max_length=80, verbose_name="sobrenome"),
            preserve_default=False,
        ),
        migrations.RunPython(split_names, rejoin_names),
        migrations.RemoveField(model_name="claim", name="name"),
        migrations.RemoveField(model_name="claim", name="phone"),
    ]
