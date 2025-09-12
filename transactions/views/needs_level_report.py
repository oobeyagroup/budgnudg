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


class NeedsLevelReportView(TemplateView):
    template_name = "transactions/needs_level_report.html"

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all transactions with related data
        transactions = Transaction.objects.select_related(
            "category", "subcategory", "payoree"
        ).order_by("-date", "description")

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

        # Group transactions by category type, needs level, category, and month
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

            # Determine needs level
            needs_level = transaction.primary_needs_level()
            if not needs_level:
                needs_level = "uncategorized"

            # Determine month key
            transaction_date = transaction.date
            month_key = f"{transaction_date.year}-{transaction_date.month:02d}"

            # Group the transaction
            grouped_data[category_type][needs_level][category_name][month_key].append(
                {
                    "transaction": transaction,
                    "category_obj": category_obj,
                }
            )

        # Convert to regular dict and calculate counts and monthly totals
        organized_data = {}
        for category_type, needs_levels in grouped_data.items():
            organized_data[category_type] = {
                "needs_levels": {},
                "total_count": 0,
                "total_amount": 0,
                "monthly_totals": {
                    month["date"].strftime("%Y-%m"): 0 for month in months
                },
            }

            for needs_level, categories in needs_levels.items():
                needs_level_data = {
                    "categories": {},
                    "total_count": 0,
                    "total_amount": 0,
                    "monthly_totals": {
                        month["date"].strftime("%Y-%m"): 0 for month in months
                    },
                }

                for category_name, monthly_transactions in categories.items():
                    category_total = 0
                    category_count = 0
                    monthly_totals = {
                        month["date"].strftime("%Y-%m"): 0 for month in months
                    }
                    all_transactions = []

                    # Process each month for this category
                    for month_key, transactions_data in monthly_transactions.items():
                        month_total = sum(
                            float(t["transaction"].amount) for t in transactions_data
                        )
                        month_count = len(transactions_data)

                        monthly_totals[month_key] = month_total
                        category_total += month_total
                        category_count += month_count
                        all_transactions.extend(transactions_data)

                    needs_level_data["categories"][category_name] = {
                        "transactions": all_transactions,
                        "total_count": category_count,
                        "total_amount": category_total,
                        "monthly_totals": monthly_totals,
                        "category_obj": (
                            all_transactions[0]["category_obj"]
                            if all_transactions
                            else None
                        ),
                        "monthly_transactions": {
                            month_key: transactions_data
                            for month_key, transactions_data in monthly_transactions.items()
                        },
                    }

                    # Add to needs level totals
                    needs_level_data["total_count"] += category_count
                    needs_level_data["total_amount"] += category_total
                    for month_key, amount in monthly_totals.items():
                        # Use defensive programming to avoid KeyError
                        needs_level_data["monthly_totals"][month_key] = (
                            needs_level_data["monthly_totals"].get(month_key, 0)
                            + amount
                        )

                organized_data[category_type]["needs_levels"][
                    needs_level
                ] = needs_level_data
                organized_data[category_type]["total_count"] += needs_level_data[
                    "total_count"
                ]
                organized_data[category_type]["total_amount"] += needs_level_data[
                    "total_amount"
                ]

                # Add to category type monthly totals
                for month_key, amount in needs_level_data["monthly_totals"].items():
                    # Use defensive programming to avoid KeyError
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
                # Use defensive programming to avoid KeyError
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

        # Sort needs levels by priority order
        needs_level_order = [
            "critical",
            "core",
            "lifestyle",
            "discretionary",
            "luxury",
            "deferred",
            "uncategorized",
        ]

        # Apply sorting to categories within each needs level
        def budget_sort_key(item):
            total = item[1]["total_amount"]
            # positives: (0, -total), negatives: (1, total)
            return (0, -total) if total >= 0 else (1, total)

        for category_type in organized_data:
            for needs_level in organized_data[category_type]["needs_levels"]:
                # Sort categories within this needs level
                sorted_categories = sorted(
                    organized_data[category_type]["needs_levels"][needs_level][
                        "categories"
                    ].items(),
                    key=budget_sort_key,
                )
                organized_data[category_type]["needs_levels"][needs_level][
                    "categories"
                ] = dict(sorted_categories)

        context.update(
            {
                "organized_data": organized_data,
                "category_type_order": category_type_order,
                "needs_level_order": needs_level_order,
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
        """Export needs level report data as CSV"""
        # Get the same data as the template view
        context = self.get_context_data()

        # Create CSV response
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="needs_level_report.csv"'
        )

        writer = csv.writer(response)

        # Write header row
        header = ["Type", "Needs Level", "Category", "Total", "Count"]
        for month in context["months"]:
            header.append(month["name"])
        writer.writerow(header)

        # Write data rows for each category
        for category_type in context["category_type_order"]:
            if category_type in context["organized_data"]:
                type_data = context["organized_data"][category_type]

                for needs_level in context["needs_level_order"]:
                    if needs_level in type_data["needs_levels"]:
                        needs_level_data = type_data["needs_levels"][needs_level]

                        for category_name, category_data in needs_level_data[
                            "categories"
                        ].items():
                            row = [
                                category_type.title(),
                                needs_level.title(),
                                category_name,
                                f"{category_data['total_amount']:.2f}",
                                str(category_data["total_count"]),
                            ]

                            # Add monthly amounts
                            for month in context["months"]:
                                month_key = month["date"].strftime("%Y-%m")
                                amount = category_data["monthly_totals"].get(
                                    month_key, 0
                                )
                                row.append(f"{amount:.2f}" if amount != 0 else "0.00")

                            writer.writerow(row)

        return response
