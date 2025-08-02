import csv
import json
import os
from django.core.management.base import BaseCommand

MAPPING_FILE = "csv_mappings.json"

class Command(BaseCommand):
    help = "Prototype CLI to map CSV headers to Transaction model fields and save mapping for reuse."

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str)

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        if not os.path.exists(csv_file):
            self.stderr.write(f"File not found: {csv_file}")
            return

        with open(csv_file, newline='') as f:
            reader = csv.reader(f)
            headers = next(reader)
            self.stdout.write("CSV Headers detected:")
            for i, header in enumerate(headers):
                self.stdout.write(f"{i+1}. {header}")

        transaction_fields = [
            'source', 'bank_account', 'sheet_account', 'date', 'description',
            'amount', 'account_type', 'check_num', 'payoree', 'memo'
        ]

        self.stdout.write("\nMap each CSV header to a Transaction field (or leave blank to skip):")
        mapping = {}
        for header in headers:
            while True:
                self.stdout.write(f"\nCSV Column: '{header}'")
                self.stdout.write(f"Available fields: {', '.join(transaction_fields)}")
                field = input("Map to field: ").strip()
                if field == "" or field in transaction_fields:
                    if field:
                        mapping[header] = field
                    break
                else:
                    self.stdout.write("Invalid field. Try again.")

        profile_name = input("Enter a name for this mapping profile: ").strip()
        if os.path.exists(MAPPING_FILE):
            with open(MAPPING_FILE, 'r') as f:
                all_mappings = json.load(f)
        else:
            all_mappings = {}

        all_mappings[profile_name] = {
            'headers': headers,
            'mapping': mapping
        }

        with open(MAPPING_FILE, 'w') as f:
            json.dump(all_mappings, f, indent=2)

        self.stdout.write(self.style.SUCCESS(f"Mapping profile '{profile_name}' saved to {MAPPING_FILE}"))