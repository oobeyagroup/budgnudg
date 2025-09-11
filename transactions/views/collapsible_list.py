from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.db.models import Count, Q
from django.http import HttpResponse
import csv
from transactions.models import Transaction, Category
from transactions.utils import trace
from collections import defaultdict
from datetime import datetime, date
import calendar
import logging

logger = logging.getLogger(__name__)


class CollapsibleTransactionListView(TemplateView):
    template_name = "transactions/budget_report.html"

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all transactions with related data, filtered to last 12 months
        # Calculate the date range for the last 12 months
        today = date.today()
        start_date = (
            date(today.year - 1, today.month, 1)
            if today.month > 1
            else date(today.year - 1, 12, 1)
        )

        transactions = (
            Transaction.objects.select_related("category", "subcategory", "payoree")
            .filter(date__gte=start_date)
            .order_by("-date", "description")
        )

        # Generate list of last 12 months including current month
        today = date.today()
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
                }
            )
        months.reverse()  # Show oldest to newest

        # Group transactions by category type, category, subcategory, and month
        grouped_data = defaultdict(
            lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        )

        for transaction in transactions:
            # Determine category type
            if transaction.category:
                category_type = transaction.category.type
                category_name = transaction.category.name
                category_obj = transaction.category
            else:
                category_type = "uncategorized"
                category_name = "Uncategorized"
                category_obj = None

            # Determine subcategory
            if transaction.subcategory:
                subcategory_name = transaction.subcategory.name
                subcategory_obj = transaction.subcategory
            else:
                subcategory_name = "No Subcategory"
                subcategory_obj = None

            # Determine month key
            transaction_date = transaction.date
            month_key = f"{transaction_date.year}-{transaction_date.month:02d}"

            # Group the transaction
            grouped_data[category_type][category_name][subcategory_name][
                month_key
            ].append(
                {
                    "transaction": transaction,
                    "category_obj": category_obj,
                    "subcategory_obj": subcategory_obj,
                }
            )

        # Convert to regular dict and calculate counts and monthly totals
        organized_data = {}
        for category_type, categories in grouped_data.items():
            organized_data[category_type] = {
                "categories": {},
                "total_count": 0,
                "total_amount": 0,
                "monthly_totals": {
                    month["date"].strftime("%Y-%m"): 0 for month in months
                },
            }

            for category_name, subcategories in categories.items():
                category_data = {
                    "subcategories": {},
                    "total_count": 0,
                    "total_amount": 0,
                    "category_obj": None,
                    "monthly_totals": {
                        month["date"].strftime("%Y-%m"): 0 for month in months
                    },
                }

                for subcategory_name, monthly_transactions in subcategories.items():
                    subcategory_total = 0
                    subcategory_count = 0
                    monthly_totals = {
                        month["date"].strftime("%Y-%m"): 0 for month in months
                    }
                    all_transactions = []

                    # Process each month for this subcategory
                    for month_key, transactions_data in monthly_transactions.items():
                        month_total = sum(
                            float(t["transaction"].amount) for t in transactions_data
                        )
                        month_count = len(transactions_data)

                        monthly_totals[month_key] = month_total
                        subcategory_total += month_total
                        subcategory_count += month_count
                        all_transactions.extend(transactions_data)

                    category_data["subcategories"][subcategory_name] = {
                        "transactions": all_transactions,
                        "count": subcategory_count,
                        "total_amount": subcategory_total,
                        "monthly_totals": monthly_totals,
                        "subcategory_obj": (
                            all_transactions[0]["subcategory_obj"]
                            if all_transactions
                            else None
                        ),
                    }

                    # Set category object from first transaction
                    if not category_data["category_obj"] and all_transactions:
                        category_data["category_obj"] = all_transactions[0][
                            "category_obj"
                        ]

                    # Add to category totals
                    category_data["total_count"] += subcategory_count
                    category_data["total_amount"] += subcategory_total
                    logger.debug(f"Category_data: {category_data}")
                    logger.debug(f"Monthly Totals: {monthly_totals}")
                    for month_key, amount in monthly_totals.items():
                        category_data["monthly_totals"][month_key] = (
                            category_data["monthly_totals"].get(month_key, 0) + amount
                        )

                organized_data[category_type]["categories"][
                    category_name
                ] = category_data
                organized_data[category_type]["total_count"] += category_data[
                    "total_count"
                ]
                organized_data[category_type]["total_amount"] += category_data[
                    "total_amount"
                ]

                # Add to category type monthly totals
                for month_key, amount in category_data["monthly_totals"].items():
                    organized_data[category_type]["monthly_totals"][month_key] = (
                        organized_data[category_type]["monthly_totals"].get(
                            month_key, 0
                        )
                        + amount
                    )

        # Calculate grand totals including monthly
        grand_total_count = sum(data["total_count"] for data in organized_data.values())
        grand_total_amount = sum(
            data["total_amount"] for data in organized_data.values()
        )
        grand_monthly_totals = {month["date"].strftime("%Y-%m"): 0 for month in months}

        for data in organized_data.values():
            for month_key, amount in data["monthly_totals"].items():
                grand_monthly_totals[month_key] = (
                    grand_monthly_totals.get(month_key, 0) + amount
                )

        # Sort category types for consistent display
        category_type_order = [
            "income",
            "expense",
            "transfer",
            "asset",
            "liability",
            "equity",
            "uncategorized",
        ]

        # Apply payoree-style sorting to categories and subcategories within each category type
        # Custom sort: positive totals descending, negative totals ascending, positives before negatives
        def budget_sort_key(item):
            total = item[1]["total_amount"]
            # positives: (0, -total), negatives: (1, total)
            return (0, -total) if total >= 0 else (1, total)

        for category_type in organized_data:
            # Sort categories within this category type
            sorted_categories = sorted(
                organized_data[category_type]["categories"].items(), key=budget_sort_key
            )

            # Sort subcategories within each category
            sorted_category_dict = {}
            for category_name, category_data in sorted_categories:
                sorted_subcategories = sorted(
                    category_data["subcategories"].items(), key=budget_sort_key
                )
                category_data["subcategories"] = dict(sorted_subcategories)
                sorted_category_dict[category_name] = category_data

            organized_data[category_type]["categories"] = sorted_category_dict

        context.update(
            {
                "organized_data": organized_data,
                "category_type_order": category_type_order,
                "months": months,
                "grand_total_count": grand_total_count,
                "grand_total_amount": grand_total_amount,
                "grand_monthly_totals": grand_monthly_totals,
                "total_transactions": transactions.count(),
            }
        )

        return context

    @method_decorator(trace)
    def get(self, request, *args, **kwargs):
        # Check if CSV export is requested
        if request.GET.get("format") == "csv":
            return self.export_csv(request)
        return super().get(request, *args, **kwargs)

    def export_csv(self, request):
        """Export budget report data as CSV"""
        # Get the same data as the template view
        context = self.get_context_data()

        # Create CSV response
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="budget_report.csv"'

        writer = csv.writer(response)

        # Write header row
        header = ["Type", "Category", "Total", "Count"]
        for month in context["months"]:
            header.append(month["name"])
        writer.writerow(header)

        # Write data rows for each category
        for category_type in context["category_type_order"]:
            if category_type in context["organized_data"]:
                type_data = context["organized_data"][category_type]

                for category_name, category_data in type_data["categories"].items():
                    row = [
                        category_type.title(),
                        category_name,
                        f"{category_data['total_amount']:.2f}",
                        str(category_data["total_count"]),
                    ]

                    # Add monthly amounts
                    for month in context["months"]:
                        month_key = month["date"].strftime("%Y-%m")
                        amount = category_data["monthly_totals"].get(month_key, 0)
                        row.append(f"{amount:.2f}" if amount != 0 else "0.00")

                    writer.writerow(row)

        return response
