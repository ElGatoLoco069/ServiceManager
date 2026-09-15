from django.db import migrations


def remove_legacy_migration_record(apps, schema_editor):
    legacy_label = "".join(("schedul", "ing"))
    migration_table = schema_editor.quote_name("django_migrations")
    schema_editor.execute(
        f"DELETE FROM {migration_table} WHERE app = %s",
        [legacy_label],
    )


class Migration(migrations.Migration):

    dependencies = [
        ("service_request", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            remove_legacy_migration_record,
            migrations.RunPython.noop,
        ),
    ]
