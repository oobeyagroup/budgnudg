"""
Baseline Calculator Service

Calculates historical spending baselines for budget suggestions using
existing transaction data and categorization patterns.
"""

from typing import Dict, List, Tuple, Optional, Any
from decimal import Decimal
from datetime import date, timedelta
from collections import defaultdict
import statistics

from django.db.models import Sum, Avg, Q, Count
from django.db.models.query import QuerySet

from transactions.models import Transaction, Category, Payoree
from transactions.utils import trace


class BaselineCalculator:
    """Calculate historical spending baselines for budget suggestions."""

    def __init__(self, lookback_months: int = 12):
        self.lookback_months = lookback_months

    def _is_operational_transaction(self, transaction) -> bool:
        """
        Identify transactions that represent operational income/expenses
        which should be included in spending baselines.

        Only includes transactions categorized as 'income' or 'expense' types.
        Excludes transfers, assets, liabilities, and equity transactions.
        """
        # Only include transactions with income or expense categories
        if transaction.category and transaction.category.type in ["income", "expense"]:
            return True

        # If no category assigned, exclude from baselines (needs categorization first)
        return False

    def _filter_operational_transactions(self, transactions):
        """
        Filter transactions to include only operational income and expenses
        that should be included in spending baselines.

        Excludes transfers, investments, and other non-operational transactions
        by filtering based on category type.
        """
        operational_transactions = []

        for txn in transactions:
            if self._is_operational_transaction(txn):
                operational_transactions.append(txn)

        return operational_transactions

    @trace
    def calculate_baselines(
        self, end_date: Optional[date] = None, method: str = "median"
    ) -> Dict[Tuple, Dict[str, Any]]:
        """
        Calculate baseline spending by scope (category, subcategory, payoree, needs_level).

        Returns dict keyed by (category_id, subcategory_id, payoree_id, needs_level)
        with values containing baseline amount and supporting statistics.
        """
        if not end_date:
            end_date = date.today()

        start_date = end_date - timedelta(days=30 * self.lookback_months)

        # Get transactions in the lookback period
        transactions = Transaction.objects.filter(
            date__gte=start_date, date__lt=end_date
        ).select_related("category", "payoree")

        # Filter out debt service transactions
        operational_transactions = self._filter_operational_transactions(transactions)

        return self._aggregate_by_scope(operational_transactions, method)

    @trace
    def calculate_month_specific_baselines(
        self,
        target_month: int,
        target_year: int,
        method: str = "median",
        lookback_years: int = 3,
    ) -> Dict[Tuple, Dict[str, Any]]:
        """
        Calculate baseline spending for a specific target month using historical data
        from the same month in previous years.

        Args:
            target_month: Month (1-12) to generate baselines for
            target_year: Year of target month (used to exclude future data)
            method: Calculation method (median, avg6, trimmed_mean)
            lookback_years: How many years of historical data to consider

        Returns:
            Dict keyed by (category_id, subcategory_id, payoree_id, needs_level)
            with baseline amounts specific to the target month.
        """
        # Get transactions from the target month in previous years
        transactions = []
        current_year = target_year - 1  # Start with previous year

        for year_offset in range(lookback_years):
            year = current_year - year_offset

            # Skip if this would be in the future
            if year >= target_year:
                continue

            # Get transactions for this month/year
            month_start = date(year, target_month, 1)
            # Calculate last day of month
            if target_month == 12:
                month_end = date(year + 1, 1, 1)
            else:
                month_end = date(year, target_month + 1, 1)

            month_transactions = Transaction.objects.filter(
                date__gte=month_start, date__lt=month_end
            ).select_related("category", "payoree")

            transactions.extend(month_transactions)

        # Filter out debt service transactions before aggregating
        operational_transactions = self._filter_operational_transactions(transactions)

        # If we don't have enough month-specific data, fall back to general baseline
        # with a preference for similar seasonal months
        if len(operational_transactions) < 10:  # Threshold for meaningful data
            return self._calculate_seasonal_fallback(target_month, target_year, method)

        return self._aggregate_by_scope_monthly(
            operational_transactions, method, target_month
        )

    def _calculate_seasonal_fallback(
        self, target_month: int, target_year: int, method: str
    ) -> Dict[Tuple, Dict[str, Any]]:
        """
        Fallback calculation when insufficient month-specific data is available.
        Uses data from similar seasonal months or general baseline.
        """
        # Try to use similar seasonal months (same quarter)
        quarter_months = {
            1: [1, 2, 3],  # Q1: Winter
            2: [1, 2, 3],  # Q1: Winter
            3: [1, 2, 3],  # Q1: Winter
            4: [4, 5, 6],  # Q2: Spring
            5: [4, 5, 6],  # Q2: Spring
            6: [4, 5, 6],  # Q2: Spring
            7: [7, 8, 9],  # Q3: Summer
            8: [7, 8, 9],  # Q3: Summer
            9: [7, 8, 9],  # Q3: Summer
            10: [10, 11, 12],  # Q4: Fall/Holiday
            11: [10, 11, 12],  # Q4: Fall/Holiday
            12: [10, 11, 12],  # Q4: Fall/Holiday
        }

        similar_months = quarter_months.get(target_month, [target_month])

        # Get transactions from similar months in past years
        transactions = []
        current_year = target_year - 1

        for year_offset in range(2):  # Look back 2 years for similar months
            year = current_year - year_offset
            for month in similar_months:
                month_start = date(year, month, 1)
                if month == 12:
                    month_end = date(year + 1, 1, 1)
                else:
                    month_end = date(year, month + 1, 1)

                month_transactions = Transaction.objects.filter(
                    date__gte=month_start, date__lt=month_end
                ).select_related("category", "payoree")

                transactions.extend(month_transactions)

        # If still insufficient data, fall back to general baseline
        if len(transactions) < 5:
            return self.calculate_baselines(method=method)

        return self._aggregate_by_scope_monthly(transactions, method, target_month)

    def _aggregate_by_scope_monthly(
        self, transactions, method: str, target_month: Optional[int] = None
    ) -> Dict[Tuple, Dict[str, Any]]:
        """
        Aggregate transactions by scope for monthly calculations.
        Groups transactions by month and scope, then calculates monthly totals,
        then takes baseline of those monthly totals (same logic as original method).
        """
        # Group transactions by month and scope (same as original method)
        monthly_data = defaultdict(lambda: defaultdict(list))

        for txn in transactions:
            # Extract effective needs level using Transaction's existing logic
            needs_levels = txn.effective_needs_levels()
            primary_level = (
                max(needs_levels, key=needs_levels.get) if needs_levels else None
            )

            scope_key = (
                txn.category_id,
                txn.subcategory_id if hasattr(txn, "subcategory") else None,
                txn.payoree_id,
                primary_level,
            )

            month_key = (txn.date.year, txn.date.month)
            monthly_data[scope_key][month_key].append(abs(float(txn.amount)))

        # Calculate monthly totals and then baseline for each scope (same as original method)
        baselines = {}
        for scope_key, months in monthly_data.items():
            monthly_totals = [sum(amounts) for amounts in months.values()]

            if not monthly_totals:
                continue

            baseline = self._calculate_baseline(monthly_totals, method)

            baselines[scope_key] = {
                "monthly_baseline": Decimal(str(baseline)),
                "support": {
                    "n_months": len(monthly_totals),
                    "min_monthly": min(monthly_totals) if monthly_totals else 0,
                    "max_monthly": max(monthly_totals) if monthly_totals else 0,
                    "total_transactions": sum(
                        len(amounts) for amounts in months.values()
                    ),
                    "method": method,
                    "target_month": target_month,
                },
            }

        return baselines

    def _aggregate_by_scope(
        self, transactions: QuerySet, method: str
    ) -> Dict[Tuple, Dict[str, Any]]:
        """Aggregate transactions by scope and calculate baselines."""

        # Group transactions by month and scope
        monthly_data = defaultdict(lambda: defaultdict(list))

        for txn in transactions:
            # Extract effective needs level using Transaction's existing logic
            needs_levels = txn.effective_needs_levels()
            primary_level = (
                max(needs_levels, key=needs_levels.get) if needs_levels else None
            )

            scope_key = (
                txn.category_id,
                txn.subcategory_id if hasattr(txn, "subcategory") else None,
                txn.payoree_id,
                primary_level,
            )

            month_key = (txn.date.year, txn.date.month)
            monthly_data[scope_key][month_key].append(abs(float(txn.amount)))

        # Calculate monthly totals and then baseline for each scope
        baselines = {}
        for scope_key, months in monthly_data.items():
            monthly_totals = [sum(amounts) for amounts in months.values()]

            if not monthly_totals:
                continue

            baseline = self._calculate_baseline(monthly_totals, method)

            baselines[scope_key] = {
                "monthly_baseline": Decimal(str(baseline)),
                "support": {
                    "n_months": len(monthly_totals),
                    "min_monthly": min(monthly_totals),
                    "max_monthly": max(monthly_totals),
                    "total_transactions": sum(
                        len(amounts) for amounts in months.values()
                    ),
                },
            }

        return self._apply_precedence_rules(baselines)

    def _calculate_baseline(self, monthly_amounts: List[float], method: str) -> float:
        """Calculate baseline using specified method."""
        if not monthly_amounts:
            return 0.0

        if method == "median":
            return statistics.median(monthly_amounts)
        elif method == "avg6":
            # Average of last 6 months
            recent_months = (
                monthly_amounts[-6:] if len(monthly_amounts) >= 6 else monthly_amounts
            )
            return sum(recent_months) / len(recent_months)
        elif method == "trimmed_mean":
            # Remove top and bottom 20%
            sorted_amounts = sorted(monthly_amounts)
            n = len(sorted_amounts)
            trim_count = max(1, int(0.2 * n))
            if n > 2 * trim_count:
                trimmed = sorted_amounts[trim_count:-trim_count]
                return sum(trimmed) / len(trimmed)
            else:
                return statistics.median(sorted_amounts)
        else:
            # Default to median
            return statistics.median(monthly_amounts)

    def _apply_precedence_rules(
        self, baselines: Dict[Tuple, Dict[str, Any]]
    ) -> Dict[Tuple, Dict[str, Any]]:
        """
        Apply precedence rules: category > subcategory > payoree
        Following the existing Transaction categorization precedence.
        """
        # Group by category and needs level
        by_category = defaultdict(list)

        for scope_key in baselines:
            category_id, subcategory_id, payoree_id, needs_level = scope_key
            category_key = (category_id, needs_level)
            by_category[category_key].append(scope_key)

        final_baselines = {}

        for (category_id, needs_level), scope_keys in by_category.items():
            # Check if there's a category-only entry (subcategory_id and payoree_id are None)
            category_only_keys = [
                k
                for k in scope_keys
                if k[1] is None
                and k[2] is None  # subcategory_id and payoree_id are None
            ]

            if category_only_keys:
                # Use category-level baseline, suppress more specific entries
                for key in category_only_keys:
                    final_baselines[key] = baselines[key]
            else:
                # Check for subcategory-level entries
                subcategory_keys = [
                    k
                    for k in scope_keys
                    if k[1] is not None and k[2] is None  # has subcategory, no payoree
                ]

                if subcategory_keys:
                    # Use subcategory-level baselines
                    for key in subcategory_keys:
                        final_baselines[key] = baselines[key]
                else:
                    # Use payoree-level baselines
                    for key in scope_keys:
                        final_baselines[key] = baselines[key]

        return final_baselines

    @trace
    def suggest_budget_amounts(
        self,
        baselines: Dict[Tuple, Dict[str, Any]],
        adjustment_factors: Optional[Dict[str, float]] = None,
    ) -> Dict[Tuple, Decimal]:
        """
        Apply AI/ML suggestions to baseline amounts.

        Uses needs_level to apply different adjustment strategies:
        - critical/core: Conservative (baseline or slightly higher)
        - lifestyle/discretionary: Target reduction (-10% to -5%)
        - luxury/deferred: Aggressive reduction (-20% to -10%)
        """
        if not adjustment_factors:
            adjustment_factors = {
                "critical": 1.05,  # 5% buffer for essentials
                "core": 1.02,  # 2% buffer
                "lifestyle": 0.95,  # 5% reduction target
                "discretionary": 0.90,  # 10% reduction target
                "luxury": 0.85,  # 15% reduction target
                "deferred": 0.80,  # 20% reduction target
            }

        suggestions = {}

        for scope_key, data in baselines.items():
            category_id, subcategory_id, payoree_id, needs_level = scope_key
            baseline = data["monthly_baseline"]

            # Apply adjustment factor based on needs level
            factor = adjustment_factors.get(needs_level, 1.0)
            suggested_amount = baseline * Decimal(str(factor))

            # Round to nearest dollar for cleaner budgets
            suggested_amount = suggested_amount.quantize(Decimal("1"))

            suggestions[scope_key] = suggested_amount

        return suggestions

    @trace
    def get_category_suggestions(
        self, target_months: int = 3, method: str = "median"
    ) -> List[Dict[str, Any]]:
        """
        Generate a list of budget suggestions ready for the wizard UI.

        Returns list of dicts with keys: category_id, subcategory_id, payoree_id,
        needs_level, baseline_amount, suggested_amount, supporting_data
        """
        baselines = self.calculate_baselines(method=method)
        suggestions = self.suggest_budget_amounts(baselines)

        result = []

        for scope_key, suggested_amount in suggestions.items():
            category_id, subcategory_id, payoree_id, needs_level = scope_key
            baseline_data = baselines[scope_key]

            # Look up related objects for display
            category_name = None
            subcategory_name = None
            payoree_name = None

            if category_id:
                try:
                    category = Category.objects.get(id=category_id)
                    category_name = category.name
                except Category.DoesNotExist:
                    pass

            if subcategory_id:
                try:
                    subcategory = Category.objects.get(id=subcategory_id)
                    subcategory_name = subcategory.name
                except Category.DoesNotExist:
                    pass

            if payoree_id:
                try:
                    payoree = Payoree.objects.get(id=payoree_id)
                    payoree_name = payoree.name
                except Payoree.DoesNotExist:
                    pass

            result.append(
                {
                    "category_id": category_id,
                    "subcategory_id": subcategory_id,
                    "payoree_id": payoree_id,
                    "needs_level": needs_level,
                    "category_name": category_name,
                    "subcategory_name": subcategory_name,
                    "payoree_name": payoree_name,
                    "baseline_amount": baseline_data["monthly_baseline"],
                    "suggested_amount": suggested_amount,
                    "support": baseline_data["support"],
                    "variance": suggested_amount - baseline_data["monthly_baseline"],
                    "variance_pct": (
                        float(
                            (suggested_amount - baseline_data["monthly_baseline"])
                            / baseline_data["monthly_baseline"]
                            * 100
                        )
                        if baseline_data["monthly_baseline"]
                        else 0
                    ),
                }
            )

        # Sort by category name, then by amount (largest first)
        result.sort(
            key=lambda x: (x["category_name"] or "ZZZ", -float(x["suggested_amount"]))
        )

        return result

    @trace
    def get_month_specific_category_suggestions(
        self, target_month: int, target_year: int, method: str = "median"
    ) -> List[Dict[str, Any]]:
        """
        Generate month-specific budget suggestions for a given target month.

        Args:
            target_month: Month (1-12) to generate suggestions for
            target_year: Year of target month
            method: Calculation method (median, avg6, trimmed_mean)

        Returns:
            List of dicts with category suggestions specific to the target month
        """
        baselines = self.calculate_month_specific_baselines(
            target_month=target_month, target_year=target_year, method=method
        )
        suggestions = self.suggest_budget_amounts(baselines)

        result = []

        for scope_key, suggested_amount in suggestions.items():
            category_id, subcategory_id, payoree_id, needs_level = scope_key
            baseline_data = baselines[scope_key]

            # Look up related objects for display
            category_name = None
            subcategory_name = None
            payoree_name = None

            if category_id:
                try:
                    category = Category.objects.get(id=category_id)
                    category_name = category.name
                except Category.DoesNotExist:
                    pass

            if subcategory_id:
                try:
                    subcategory = Category.objects.get(id=subcategory_id)
                    subcategory_name = subcategory.name
                except Category.DoesNotExist:
                    pass

            if payoree_id:
                try:
                    payoree = Payoree.objects.get(id=payoree_id)
                    payoree_name = payoree.name
                except Payoree.DoesNotExist:
                    pass

            result.append(
                {
                    "category_id": category_id,
                    "subcategory_id": subcategory_id,
                    "payoree_id": payoree_id,
                    "needs_level": needs_level,
                    "category_name": category_name,
                    "subcategory_name": subcategory_name,
                    "payoree_name": payoree_name,
                    "baseline_amount": baseline_data["monthly_baseline"],
                    "suggested_amount": suggested_amount,
                    "support": baseline_data["support"],
                    "variance": suggested_amount - baseline_data["monthly_baseline"],
                    "variance_pct": (
                        float(
                            (suggested_amount - baseline_data["monthly_baseline"])
                            / baseline_data["monthly_baseline"]
                            * 100
                        )
                        if baseline_data["monthly_baseline"]
                        else 0
                    ),
                    "target_month": target_month,
                    "target_year": target_year,
                }
            )

        # Sort by category name, then by amount (largest first)
        result.sort(
            key=lambda x: (x["category_name"] or "ZZZ", -float(x["suggested_amount"]))
        )

        return result
