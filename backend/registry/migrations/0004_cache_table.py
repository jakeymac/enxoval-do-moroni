"""Creates the table behind DatabaseCache.

The claim rate limit counts through the cache. Creating the table here rather
than leaving `createcachetable` as a deploy step means every environment that
runs migrations — production, a fresh clone, the test database — has it, and
there is no way to start the app with rate limiting silently broken.
"""
from django.core.management import call_command
from django.db import migrations

TABLE = "django_cache"


def create_cache_table(apps, schema_editor):
    # createcachetable is a no-op when the table is already there.
    call_command("createcachetable", TABLE, database=schema_editor.connection.alias, verbosity=0)


def drop_cache_table(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {schema_editor.connection.ops.quote_name(TABLE)}")


class Migration(migrations.Migration):

    dependencies = [("registry", "0003_alter_claim_options_alter_item_options_and_more")]

    operations = [migrations.RunPython(create_cache_table, drop_cache_table)]
