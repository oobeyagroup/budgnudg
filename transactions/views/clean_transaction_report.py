"""
Clean Transaction Monthly Report View
Provides a glassmorphism table showing transaction summary by category and month
"""

from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.db.models import Sum, Count
from datetime import date, datetime
from collections import defaultdict
from transactions.models import Transaction
from transactions.utils import trace
import calendar


class CleanTransactionReportView(TemplateView):
    template_name = "transactions/clean_transaction_report.html"

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get last 6 months of data for a cleaner view
        today = date.today()
        start_date = date(today.year, max(1, today.month - 5), 1)

        # Get transactions with category data
        transactions = (
            Transaction.objects.select_related("category", "subcategory")
            .filter(date__gte=start_date)
            .order_by("-date")
        )

        # Generate month headers
        months = []
        for i in range(6):
            year = today.year
            month = today.month - i
            if month <= 0:
                month += 12
                year -= 1
            months.append(
                {
                    "name": calendar.month_abbr[month],
                    "year": year,
                    "month": month,
                    "key": f"{year}-{month:02d}",
                }
            )
        months.reverse()  # Show oldest to newest

        # Group transactions by category and month
        from decimal import Decimal

        category_data = defaultdict(
            lambda: {
                "total_amount": Decimal("0"),
                "total_count": 0,
                "monthly_amounts": defaultdict(lambda: Decimal("0")),
                "monthly_counts": defaultdict(int),
                "transactions": [],
            }
        )

        grand_total = Decimal("0")
        grand_count = 0
        monthly_totals = defaultdict(lambda: Decimal("0"))

        for txn in transactions:
            category_name = txn.category.name if txn.category else "Uncategorized"
            month_key = f"{txn.date.year}-{txn.date.month:02d}"

            # Update category totals
            category_data[category_name]["total_amount"] += txn.amount
            category_data[category_name]["total_count"] += 1
            category_data[category_name]["monthly_amounts"][month_key] += txn.amount
            category_data[category_name]["monthly_counts"][month_key] += 1
            category_data[category_name]["transactions"].append(txn)

            # Update grand totals
            grand_total += txn.amount
            grand_count += 1
            monthly_totals[month_key] += txn.amount

        # Sort categories by total amount (highest expense/lowest income first)
        sorted_categories = sorted(
            category_data.items(), key=lambda x: x[1]["total_amount"]
        )

        context.update(
            {
                "months": months,
                "category_data": dict(sorted_categories),
                "grand_total": grand_total,
                "grand_count": grand_count,
                "monthly_totals": dict(monthly_totals),
                "transaction_count": transactions.count(),
            }
        )

        return context
