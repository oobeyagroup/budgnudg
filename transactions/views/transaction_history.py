# transactions/views/transaction_history.py
from django.views.generic import ListView
from django.db.models import Q, Count
from django.utils.decorators import method_decorator
from collections import defaultdict, OrderedDict
from datetime import date, timedelta
from transactions.models import Transaction
from transactions.utils import trace
from ingest.models import FinancialAccount
import logging

logger = logging.getLogger(__name__)


class TransactionHistoryView(ListView):
    """Transaction history view showing transactions grouped by day, then by category."""

    template_name = "transactions/transaction_history.html"
    context_object_name = "grouped_transactions"
    ordering = "-date"

    @method_decorator(trace)
    def get_queryset(self):
        """Get transactions with related data, applying filters."""
        queryset = Transaction.objects.select_related(
            "category", "subcategory", "payoree", "bank_account"
        ).prefetch_related("tags")

        # Apply filters
        queryset = self._apply_filters(queryset)

        # Order by date (newest first), then by category, then by amount (largest first)
        return queryset.order_by("-date", "category__name", "-amount")

    def _apply_filters(self, queryset):
        """Apply various filters based on GET parameters."""

        # Date range filter
        days_back = self.request.GET.get("days", "30")
        try:
            days_back = int(days_back)
            start_date = date.today() - timedelta(days=days_back)
            queryset = queryset.filter(date__gte=start_date)
        except (ValueError, TypeError):
            # Default to last 30 days if invalid input
            start_date = date.today() - timedelta(days=30)
            queryset = queryset.filter(date__gte=start_date)

        # Bank account filter
        account = self.request.GET.get("account")
        if account:
            queryset = queryset.filter(bank_account__name=account)

        # Category filter
        category = self.request.GET.get("category")
        if category:
            queryset = queryset.filter(category__name__icontains=category)

        # Amount range filter
        amount_min = self.request.GET.get("amount_min")
        amount_max = self.request.GET.get("amount_max")
        if amount_min:
            try:
                queryset = queryset.filter(amount__gte=float(amount_min))
            except ValueError:
                pass
        if amount_max:
            try:
                queryset = queryset.filter(amount__lte=float(amount_max))
            except ValueError:
                pass

        # Transaction type filter (income/expense)
        tx_type = self.request.GET.get("type")
        if tx_type == "income":
            queryset = queryset.filter(amount__gt=0)
        elif tx_type == "expense":
            queryset = queryset.filter(amount__lt=0)

        # Search filter
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(description__icontains=search)
                | Q(payoree__name__icontains=search)
                | Q(memo__icontains=search)
            )

        # Categorization status filter
        status = self.request.GET.get("status")
        if status == "uncategorized":
            queryset = queryset.filter(category__isnull=True)
        elif status == "no_payoree":
            queryset = queryset.filter(payoree__isnull=True)

        return queryset

    @method_decorator(trace)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Group transactions by date, then by category
        transactions = self.get_queryset()
        grouped_data = self._group_transactions_by_date_and_category(transactions)

        context["grouped_transactions"] = grouped_data
        context["current_filters"] = self._get_current_filters()
        context["available_accounts"] = FinancialAccount.objects.all().order_by("name")
        context["stats"] = self._calculate_stats(transactions)

        return context

    def _group_transactions_by_date_and_category(self, transactions):
        """Group transactions by date, then by category within each date."""
        grouped = OrderedDict()

        for transaction in transactions:
            tx_date = transaction.date
            category_name = (
                transaction.category.name if transaction.category else "Uncategorized"
            )

            # Initialize date group if not exists
            if tx_date not in grouped:
                grouped[tx_date] = {
                    "date": tx_date,
                    "categories": OrderedDict(),
                    "total_income": 0,
                    "total_expense": 0,
                    "net_total": 0,
                    "transaction_count": 0,
                }

            # Initialize category group within date if not exists
            if category_name not in grouped[tx_date]["categories"]:
                grouped[tx_date]["categories"][category_name] = {
                    "category": transaction.category,
                    "transactions": [],
                    "total_amount": 0,
                    "income_amount": 0,
                    "expense_amount": 0,
                    "transaction_count": 0,
                }

            # Add transaction to appropriate group
            category_group = grouped[tx_date]["categories"][category_name]
            category_group["transactions"].append(transaction)
            category_group["total_amount"] += transaction.amount
            category_group["transaction_count"] += 1

            # Update category totals
            if transaction.amount > 0:
                category_group["income_amount"] += transaction.amount
            else:
                category_group["expense_amount"] += abs(transaction.amount)

            # Update daily totals
            day_group = grouped[tx_date]
            day_group["transaction_count"] += 1
            day_group["net_total"] += transaction.amount

            if transaction.amount > 0:
                day_group["total_income"] += transaction.amount
            else:
                day_group["total_expense"] += abs(transaction.amount)

        return grouped

    def _get_current_filters(self):
        """Extract current filter values from request."""
        return {
            "days": self.request.GET.get("days", "30"),
            "account": self.request.GET.get("account", ""),
            "category": self.request.GET.get("category", ""),
            "amount_min": self.request.GET.get("amount_min", ""),
            "amount_max": self.request.GET.get("amount_max", ""),
            "type": self.request.GET.get("type", ""),
            "search": self.request.GET.get("search", ""),
            "status": self.request.GET.get("status", ""),
        }

    def _calculate_stats(self, transactions):
        """Calculate summary statistics for the filtered transactions."""
        if not transactions:
            return {
                "total_transactions": 0,
                "total_income": 0,
                "total_expense": 0,
                "net_total": 0,
                "avg_transaction": 0,
                "unique_categories": 0,
                "unique_payorees": 0,
            }

        total_income = sum(t.amount for t in transactions if t.amount > 0)
        total_expense = sum(abs(t.amount) for t in transactions if t.amount < 0)
        net_total = total_income - total_expense

        unique_categories = len(
            set(
                t.category.name if t.category else "Uncategorized" for t in transactions
            )
        )
        unique_payorees = len(
            set(t.payoree.name if t.payoree else "Unknown" for t in transactions)
        )

        return {
            "total_transactions": len(transactions),
            "total_income": total_income,
            "total_expense": total_expense,
            "net_total": net_total,
            "avg_transaction": (
                (total_income - total_expense) / len(transactions)
                if transactions
                else 0
            ),
            "unique_categories": unique_categories,
            "unique_payorees": unique_payorees,
        }
