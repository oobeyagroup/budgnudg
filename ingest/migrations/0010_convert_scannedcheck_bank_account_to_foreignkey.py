# Simple migration to convert ScannedCheck bank_account to ForeignKey
# Since user is okay with emptying ScannedCheck table, we can do this cleanly

from django.db import migrations, models
import django.db.models.deletion


def clear_scanned_checks(apps, schema_editor):
    """Delete all existing ScannedCheck records since we're okay with rebuilding."""
    ScannedCheck = apps.get_model("ingest", "ScannedCheck")
    ScannedCheck.objects.all().delete()


def reverse_migration(apps, schema_editor):
    """No reverse operation needed since we're clearing data anyway."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("ingest", "0009_rename_mappingprofile_financialaccount"),
    ]

    operations = [
        # Clear existing data first
        migrations.RunPython(clear_scanned_checks, reverse_migration),
        # Remove the old CharField
        migrations.RemoveField(
            model_name="scannedcheck",
            name="bank_account",
        ),
        # Add the new ForeignKey field
        migrations.AddField(
            model_name="scannedcheck",
            name="bank_account",
            field=models.ForeignKey(
                "ingest.FinancialAccount",
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
            ),
        ),
    ]
