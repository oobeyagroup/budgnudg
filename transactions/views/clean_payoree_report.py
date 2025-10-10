"""
Clean Payoree Report View
Provides a glassmorphism table showing transaction summary by payoree
"""
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.db.models import Sum, Count
from datetime import date
from collections import defaultdict
from transactions.models import Transaction
from transactions.utils import trace


class CleanPayoreeReportView(TemplateView):
    template_name = "transactions/clean_payoree_report.html"

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get last 3 months of data for performance
        today = date.today()
        start_date = date(today.year, max(1, today.month - 2), 1)
        
        # Get transactions with payoree data
        transactions = Transaction.objects.filter(
            date__gte=start_date
        ).order_by('-date')
        
        # Group transactions by payoree
        from decimal import Decimal
        payoree_data = defaultdict(lambda: {
            'total_amount': Decimal('0'),
            'total_count': 0,
            'transactions': [],
            'avg_amount': Decimal('0'),
            'categories': set()
        })
        
        total_amount = Decimal('0')
        total_count = 0
        
        for txn in transactions:
            payoree_name = txn.payoree or 'Unknown Payoree'
            
            # Update payoree totals
            payoree_data[payoree_name]['total_amount'] += txn.amount
            payoree_data[payoree_name]['total_count'] += 1
            payoree_data[payoree_name]['transactions'].append(txn)
            if txn.category:
                payoree_data[payoree_name]['categories'].add(txn.category.name)
            
            # Update grand totals
            total_amount += txn.amount
            total_count += 1
        
        # Calculate averages and convert categories to list
        for payoree_name, data in payoree_data.items():
            if data['total_count'] > 0:
                data['avg_amount'] = data['total_amount'] / data['total_count']
            data['categories'] = list(data['categories'])
        
        # Sort payorees by total amount (highest expense/lowest income first)
        sorted_payorees = sorted(
            payoree_data.items(),
            key=lambda x: x[1]['total_amount']
        )
        
        context.update({
            'payoree_data': dict(sorted_payorees),
            'total_amount': total_amount,
            'total_count': total_count,
            'transaction_count': transactions.count(),
            'unique_payorees': len(payoree_data),
        })
        
        return context