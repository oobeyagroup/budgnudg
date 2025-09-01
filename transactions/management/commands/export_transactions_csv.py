import csv
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Export transactions to CSV with date, description, payoree, merchant_key'

    def handle(self, *args, **options):
        from transactions.models import Transaction
        from transactions.categorization import extract_merchant_from_description

        out_path = '/tmp/transactions_export.csv'
        self.stdout.write(f'Writing CSV to {out_path}...')
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['date', 'description', 'payoree', 'merchant_key'])
            qs = Transaction.objects.select_related('payoree').order_by('date')
            for t in qs.iterator():
                date = t.date.isoformat() if getattr(t, 'date', None) is not None else ''
                desc = (t.description or '').strip()
                pay = (t.payoree.name if getattr(t, 'payoree', None) else '')
                merchant = (extract_merchant_from_description(t.description) or '').strip()
                writer.writerow([date, desc, pay, merchant])

        self.stdout.write(self.style.SUCCESS(f'WROTE: {out_path}'))
