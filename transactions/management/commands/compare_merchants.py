from collections import Counter
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Compare extracted merchant vs payoree values across transactions and write a report to /tmp/merchant_compare.txt'

    def handle(self, *args, **options):
        from transactions.models import Transaction
        from transactions.categorization import extract_merchant_from_description

        def norm(s):
            return (s or '').strip().lower()

        total = Transaction.objects.count()
        with_pay_qs = Transaction.objects.filter(payoree__isnull=False).select_related('payoree')
        count_with_pay = with_pay_qs.count()
        match_count = 0
        sample_mismatch = []
        for t in with_pay_qs.iterator():
            extracted = norm(extract_merchant_from_description(t.description))
            pay = norm(t.payoree.name) if t.payoree else ''
            if extracted and extracted == pay:
                match_count += 1
            else:
                if len(sample_mismatch) < 20:
                    sample_mismatch.append((t.id, pay, extracted, (t.description or '')[:120]))

        no_pay_qs = Transaction.objects.filter(payoree__isnull=True)
        no_pay_count = no_pay_qs.count()
        no_pay_counter = Counter()
        for t in no_pay_qs.iterator():
            extracted = norm(extract_merchant_from_description(t.description)) or 'unknown'
            no_pay_counter[extracted] += 1

        extract_counter = Counter()
        for t in Transaction.objects.iterator():
            extract_counter[norm(extract_merchant_from_description(t.description)) or 'unknown'] += 1

        out_lines = []
        out_lines.append(f'Total transactions: {total}')
        out_lines.append(f'Transactions with payoree: {count_with_pay}')
        pct = (match_count / count_with_pay) if count_with_pay else 0
        out_lines.append(f'Matches where extracted merchant == payoree name: {match_count} ({pct:.2%})')
        out_lines.append(f'Transactions without payoree: {no_pay_count}')
        out_lines.append('\nTop 20 extracted merchants for transactions without payoree:')
        for k, v in no_pay_counter.most_common(20):
            out_lines.append(f'  {v:6d}  {k}')

        out_lines.append('\nTop 30 extracted merchants overall:')
        for k, v in extract_counter.most_common(30):
            out_lines.append(f'  {v:6d}  {k}')

        out_lines.append('\nSample mismatches (up to 20):')
        for mid, pay, ext, desc in sample_mismatch:
            out_lines.append(f'{mid} payoree={pay} extracted={ext} desc={desc}')

        out_path = '/tmp/merchant_compare.txt'
        with open(out_path, 'w') as f:
            f.write('\n'.join(out_lines))

        self.stdout.write(self.style.SUCCESS(f'WROTE: {out_path}'))
        # also print a short summary to stdout
        self.stdout.write('\n'.join(out_lines[:8]))
