# transactions/management/commands/build_suggestions.py
import csv, json
from collections import Counter, defaultdict
from django.core.management.base import BaseCommand
from transactions.categorization import extract_merchant_from_description
from transactions.models import Category, Payoree, LearnedSubcat, LearnedPayoree

class Command(BaseCommand):
    help = "Train suggestion tables from history.csv using csv_mappings.json"

    def add_arguments(self, p):
        p.add_argument("--csv", default="history.csv")
        p.add_argument("--profile", default="history")  # name in csv_mappings.json
        p.add_argument("--min-count", type=int, default=2)
        p.add_argument("--dry-run", action="store_true")

    def handle(self, *a, **o):
        mappings = json.load(open("csv_mappings.json"))
        profile = mappings[o["profile"]]["mapping"]
        f = open(o["csv"], encoding="utf-8-sig")
        r = csv.DictReader(f)

        subcat_counts = defaultdict(Counter)
        payoree_counts = defaultdict(Counter)

        for row in r:
            desc = (row.get(self._rev(profile, "description")) or "").strip()
            key = extract_merchant_from_description(desc)

            # Resolve subcategory name in row (if mapped)
            subcat_name = (row.get(self._rev(profile, "subcategory")) or "").strip()
            payoree_name = (row.get(self._rev(profile, "payoree")) or "").strip()

            if key:
                if subcat_name:
                    subcat_counts[key][subcat_name] += 1
                if payoree_name:
                    payoree_counts[key][payoree_name] += 1

        if o["dry_run"]:
            self.stdout.write(f"Found {len(subcat_counts)} merchants w/ subcat; {len(payoree_counts)} with payoree")
            return

        # write to DB
        for key, counter in subcat_counts.items():
            name, cnt = counter.most_common(1)[0]
            if cnt >= o["min_count"]:
                subcat = Category.objects.filter(name=name).first()
                if subcat:
                    obj, _ = LearnedSubcat.objects.get_or_create(key=key, subcategory=subcat)
                    obj.count = cnt
                    obj.save()

        for key, counter in payoree_counts.items():
            name, cnt = counter.most_common(1)[0]
            if cnt >= o["min_count"]:
                pyo = Payoree.get_existing(name) or Payoree.objects.create(name=name)
                obj, _ = LearnedPayoree.objects.get_or_create(key=key, payoree=pyo)
                obj.count = cnt
                obj.save()

    def _rev(self, mapping, model_field):
        # find CSV column that maps to given model_field
        for csv_col, mf in mapping.items():
            if mf == model_field:
                return csv_col
        return None