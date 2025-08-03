import csv
import os
from django.core.management.base import BaseCommand
from transactions.models import Category

class Command(BaseCommand):
    help = "Import categories and subcategories from a CSV file."

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
                category_name = row.get('Category', '').strip()
                subcategory_name = row.get('SubCategory', '').strip()

                if not category_name:
                    self.stderr.write(f"Skipping row with empty Category: {row}")
                    continue

                parent_cat, _ = Category.objects.get_or_create(name=category_name, parent=None)

                if subcategory_name:
                    subcat, created = Category.objects.get_or_create(name=subcategory_name, parent=parent_cat)
                    if created:
                        created_count += 1
                else:
                    # Only count parent if it was newly created
                    if parent_cat._state.adding:
                        created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Import complete: {created_count} new categories/subcategories created."))