import json
from django.core.management.base import BaseCommand
from ingest.models import FinancialAccount


class Command(BaseCommand):
    help = "Import FinancialAccounts from a legacy csv_mappings.json"

    def add_arguments(self, parser):
        parser.add_argument("path", type=str, help="Path to csv_mappings.json")

    def handle(self, *args, **opts):
        path = opts["path"]
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Support both {name: {mapping: {...}, options: {...}, headers: [...]}}
        # and simpler {name: {...mapping...}}
        created, updated = 0, 0
        for name, payload in data.items():
            if isinstance(payload, dict) and "mapping" in payload:
                column_map = payload.get("mapping", {})
                options = payload.get("options", {})
            else:
                column_map = payload or {}
                options = {}

            obj, is_created = FinancialAccount.objects.update_or_create(
                name=name,
                defaults={"column_map": column_map, "options": options},
            )
            created += int(is_created)
            updated += int(not is_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported/updated {len(data)} profiles "
                f"(created: {created}, updated: {updated})."
            )
        )
