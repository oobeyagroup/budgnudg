"""
Clean Needs Level Report View
Provides a glassmorphism table showing transaction summary by needs level
"""
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.db.models import Sum, Count
from datetime import date
from collections import defaultdict
from transactions.models import Transaction
from transactions.utils import trace


class CleanNeedsLevelReportView(TemplateView):
    template_name = "transactions/clean_needs_level_report.html"

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get last 3 months of data for performance
        today = date.today()
        start_date = date(today.year, max(1, today.month - 2), 1)
        
        # Get transactions with category data
        transactions = Transaction.objects.filter(
            date__gte=start_date
        ).select_related('category').order_by('-date')
        
        # Group transactions by needs level
        from decimal import Decimal
        needs_data = defaultdict(lambda: {
            'total_amount': Decimal('0'),
            'total_count': 0,
            'transactions': [],
            'avg_amount': Decimal('0'),
            'categories': set()
        })
        
        total_amount = Decimal('0')
        total_count = 0
        
        for txn in transactions:
            # Determine needs level
            needs_level = txn.primary_needs_level() if hasattr(txn, 'primary_needs_level') else 'Unknown'
            if not needs_level:
                needs_level = 'Uncategorized'
            
            # Update needs level totals
            needs_data[needs_level]['total_amount'] += txn.amount
            needs_data[needs_level]['total_count'] += 1
            needs_data[needs_level]['transactions'].append(txn)
            if txn.category:
                needs_data[needs_level]['categories'].add(txn.category.name)
            
            # Update grand totals
            total_amount += txn.amount
            total_count += 1
        
        # Calculate averages and convert categories to list
        for needs_level, data in needs_data.items():
            if data['total_count'] > 0:
                data['avg_amount'] = data['total_amount'] / data['total_count']
            data['categories'] = list(data['categories'])
        
        # Sort by total amount (highest expense/lowest income first)
        sorted_needs = sorted(
            needs_data.items(),
            key=lambda x: x[1]['total_amount']
        )
        
        context.update({
            'needs_data': dict(sorted_needs),
            'total_amount': total_amount,
            'total_count': total_count,
            'transaction_count': transactions.count(),
            'unique_needs_levels': len(needs_data),
        })
        
        return context