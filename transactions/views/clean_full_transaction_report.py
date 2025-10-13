"""
Clean Full Transaction Report View
Provides a glassmorphism version of the original CollapsibleTransactionListView
"""

from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.db.models import Sum, Count
from datetime import date, datetime
from collections import defaultdict
from transactions.models import Transaction, Category
from transactions.utils import trace
import calendar
from decimal import Decimal


class CleanFullTransactionReportView(TemplateView):
    template_name = "transactions/clean_full_transaction_report.html"

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all transactions with related data, filtered to last 12 months (like original)
        today = date.today()
        start_date = date(today.year, max(1, today.month - 11), 1)

        transactions = (
            Transaction.objects.select_related("category", "subcategory", "payoree")
            .filter(date__gte=start_date)
            .order_by("-date", "description")
        )

        # Generate list of last 12 months including current month (like original)
        months = []
        for i in range(12):
            # Calculate month and year going back from current date
            year = today.year
            month = today.month - i

            # Handle year rollover
            while month <= 0:
                month += 12
                year -= 1

            month_date = date(year, month, 1)
            months.append(
                {
                    "date": month_date,
                    "name": month_date.strftime("%b %Y"),
                    "short_name": month_date.strftime("%b"),
                    "year": month_date.year,
                    "month": month_date.month,
                    "key": f"{year}-{month:02d}",
                }
            )
        months.reverse()  # Show oldest to newest

        # Group transactions by category and subcategory (simplified from original)
        category_data = defaultdict(
            lambda: {
                "name": "",
                "total_amount": Decimal("0"),
                "total_count": 0,
                "subcategories": defaultdict(
                    lambda: {
                        "name": "",
                        "transactions": [],
                        "total_amount": Decimal("0"),
                        "total_count": 0,
                        "monthly_totals": defaultdict(lambda: Decimal("0")),
                    }
                ),
                "monthly_totals": defaultdict(lambda: Decimal("0")),
            }
        )

        grand_total = Decimal("0")
        grand_count = 0
        monthly_totals = defaultdict(lambda: Decimal("0"))

        # Group by category type first, then by category name
        category_type_data = defaultdict(
            lambda: defaultdict(
                lambda: {
                    "name": "",
                    "category_type": "",
                    "category_obj": None,
                    "total_amount": Decimal("0"),
                    "total_count": 0,
                    "subcategories": defaultdict(
                        lambda: {
                            "name": "",
                            "transactions": [],
                            "total_amount": Decimal("0"),
                            "total_count": 0,
                            "monthly_totals": defaultdict(lambda: Decimal("0")),
                        }
                    ),
                    "monthly_totals": defaultdict(lambda: Decimal("0")),
                }
            )
        )

        for transaction in transactions:
            # Determine category and category type
            if transaction.category:
                category_name = transaction.category.name
                category_type = transaction.category.type
                category_obj = transaction.category
            else:
                category_name = "Uncategorized"
                category_type = "expense"  # Default uncategorized to expense
                category_obj = None

            # Determine subcategory
            if transaction.subcategory:
                subcategory_name = transaction.subcategory.name
            else:
                subcategory_name = "No Subcategory"

            # Determine month key
            month_key = f"{transaction.date.year}-{transaction.date.month:02d}"

            # Update category totals
            cat_data = category_type_data[category_type][category_name]
            cat_data["name"] = category_name
            cat_data["category_type"] = category_type
            cat_data["category_obj"] = category_obj
            cat_data["total_amount"] += transaction.amount
            cat_data["total_count"] += 1
            cat_data["monthly_totals"][month_key] += transaction.amount

            # Update subcategory data
            subcat_data = cat_data["subcategories"][subcategory_name]
            subcat_data["name"] = subcategory_name
            subcat_data["transactions"].append(
                {
                    "transaction": transaction,
                    "category_obj": transaction.category,
                    "subcategory_obj": transaction.subcategory,
                }
            )
            subcat_data["total_amount"] += transaction.amount
            subcat_data["total_count"] += 1
            subcat_data["monthly_totals"][month_key] += transaction.amount

            # Update grand totals
            grand_total += transaction.amount
            grand_count += 1
            monthly_totals[month_key] += transaction.amount

        # Convert to ordered list: Income first, then Expenses, sorted by descending absolute value within each type
        ordered_categories = []

        # Define the order we want: income first, then expenses
        type_order = ["income", "expense", "transfer", "asset", "liability", "equity"]

        for category_type in type_order:
            if category_type in category_type_data:
                # Sort categories within this type by descending absolute value
                type_categories = sorted(
                    category_type_data[category_type].items(),
                    key=lambda x: abs(x[1]["total_amount"]),
                    reverse=True,
                )

                for category_name, data in type_categories:
                    # Sort subcategories by descending absolute value too
                    clean_subcategories = {}
                    sorted_subcategories = sorted(
                        data["subcategories"].items(),
                        key=lambda x: abs(x[1]["total_amount"]),
                        reverse=True,
                    )

                    for subcat_name, subcat_data in sorted_subcategories:
                        # Sort transactions by date (newest first)
                        subcat_data["transactions"].sort(
                            key=lambda x: x["transaction"].date, reverse=True
                        )
                        clean_subcategories[subcat_name] = {
                            "name": subcat_data["name"],
                            "transactions": subcat_data["transactions"],
                            "total_amount": subcat_data["total_amount"],
                            "total_count": subcat_data["total_count"],
                            "monthly_totals": dict(subcat_data["monthly_totals"]),
                        }

                    ordered_categories.append(
                        (
                            category_name,
                            {
                                "name": data["name"],
                                "category_type": data["category_type"],
                                "category_obj": data["category_obj"],
                                "total_amount": data["total_amount"],
                                "total_count": data["total_count"],
                                "subcategories": clean_subcategories,
                                "monthly_totals": dict(data["monthly_totals"]),
                            },
                        )
                    )

        # Organize data by category type like the original
        organized_data = {}
        for category_type in type_order:
            if category_type in category_type_data:
                type_categories = category_type_data[category_type]

                # Calculate type totals
                type_total_amount = sum(
                    cat_data["total_amount"] for cat_data in type_categories.values()
                )
                type_total_count = sum(
                    cat_data["total_count"] for cat_data in type_categories.values()
                )
                type_monthly_totals = defaultdict(lambda: Decimal("0"))

                for cat_data in type_categories.values():
                    for month_key, amount in cat_data["monthly_totals"].items():
                        type_monthly_totals[month_key] += amount

                # Sort categories within type by descending absolute value
                sorted_type_categories = sorted(
                    type_categories.items(),
                    key=lambda x: abs(x[1]["total_amount"]),
                    reverse=True,
                )

                organized_data[category_type] = {
                    "categories": dict(sorted_type_categories),
                    "total_count": type_total_count,
                    "total_amount": type_total_amount,
                    "monthly_totals": dict(type_monthly_totals),
                }

        # Category type order like the original
        category_type_order = [
            "income",
            "expense",
            "transfer",
            "asset",
            "liability",
            "equity",
            "uncategorized",
        ]

        context.update(
            {
                "organized_data": organized_data,
                "category_type_order": category_type_order,
                "months": months,
                "grand_total_count": grand_count,
                "grand_total_amount": grand_total,
                "grand_monthly_totals": dict(monthly_totals),
                "transactions_count": transactions.count(),
            }
        )

        return context
