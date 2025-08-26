from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.db.models import Count
from transactions.models import Transaction, Payoree
from transactions.utils import trace
from collections import defaultdict
from datetime import date

class PayoreeReportView(TemplateView):
    template_name = "transactions/payoree_report.html"

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all transactions with related payoree
        transactions = Transaction.objects.select_related('payoree').order_by('-date', 'description')
        
        # Generate list of last 12 months including current month
        today = date.today()
        months = []
        for i in range(12):
            year = today.year
            month = today.month - i
            while month <= 0:
                month += 12
                year -= 1
            month_date = date(year, month, 1)
            months.append({
                'date': month_date,
                'name': month_date.strftime('%b %Y'),
                'short_name': month_date.strftime('%b'),
                'year': month_date.year,
                'month': month_date.month
            })
        months.reverse()

        # Group transactions by payoree
        payoree_data = defaultdict(lambda: {'transactions': [], 'monthly_totals': defaultdict(float), 'total_amount': 0, 'count': 0})
        for txn in transactions:
            if txn.payoree:
                key = txn.payoree.name
            else:
                key = None
            if key:
                payoree_data[key]['transactions'].append(txn)
                payoree_data[key]['count'] += 1
                payoree_data[key]['total_amount'] += float(txn.amount)
                month_key = f"{txn.date.year}-{txn.date.month:02d}"
                payoree_data[key]['monthly_totals'][month_key] += float(txn.amount)


        # Separate payorees with only one transaction, but only group into 'Other' if abs(total) < 250
        other_payoree = {'transactions': [], 'monthly_totals': defaultdict(float), 'total_amount': 0, 'count': 0}
        filtered_payorees = {}
        for payoree, data in payoree_data.items():
            if data['count'] == 1 and abs(data['total_amount']) < 250:
                other_payoree['transactions'].extend(data['transactions'])
                other_payoree['count'] += 1
                other_payoree['total_amount'] += data['total_amount']
                for month_key, amt in data['monthly_totals'].items():
                    other_payoree['monthly_totals'][month_key] += amt
            else:
                filtered_payorees[payoree] = data
        if other_payoree['count'] > 0:
            filtered_payorees['Other Payoree'] = other_payoree

        # Remove payorees with no transactions (shouldn't exist, but for safety)
        filtered_payorees = {k: v for k, v in filtered_payorees.items() if v['count'] > 0}

        # Calculate grand totals
        grand_total_count = sum(data['count'] for data in filtered_payorees.values())
        grand_total_amount = sum(data['total_amount'] for data in filtered_payorees.values())
        grand_monthly_totals = {month['date'].strftime('%Y-%m'): 0 for month in months}
        for data in filtered_payorees.values():
            for month_key, amt in data['monthly_totals'].items():
                grand_monthly_totals[month_key] += amt


        # Custom sort: positive totals descending, negative totals ascending, positives before negatives
        def payoree_sort_key(item):
            total = item[1]['total_amount']
            # positives: (0, -total), negatives: (1, total)
            return (0, -total) if total >= 0 else (1, total)

        sorted_payorees = sorted(
            ((k, v) for k, v in filtered_payorees.items() if k != 'Other Payoree'),
            key=payoree_sort_key
        )
        # Add 'Other Payoree' at the end if it exists
        if 'Other Payoree' in filtered_payorees:
            sorted_payorees.append(('Other Payoree', filtered_payorees['Other Payoree']))

        context.update({
            'payoree_data': sorted_payorees,
            'months': months,
            'grand_total_count': grand_total_count,
            'grand_total_amount': grand_total_amount,
            'grand_monthly_totals': grand_monthly_totals,
            'total_transactions': transactions.count(),
        })
        return context
