import csv
import os
from django.core.management.base import BaseCommand
from transactions.models import Payoree

class Command(BaseCommand):
    help = "Import payoree records from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str)

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        if not os.path.exists(csv_file):
            self.stderr.write(f"File not found: {csv_file}")
            return

        created_count = 0
        with open(csv_file, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get('Name', '').strip()
                if not name:
                    self.stderr.write(f"Skipping row with empty Name: {row}")
                    continue

                existing = Payoree.get_existing(name)
                if existing:
                    continue
                else:
                    Payoree.objects.create(name=name)
                    created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Import complete: {created_count} new payorees created."))