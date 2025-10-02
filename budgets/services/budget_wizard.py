"""
Budget Wizard Service

Orchestrates the budget creation wizard flow, integrating baseline calculations
with AI suggestions and user preferences.
"""

from typing import Dict, List, Any, Optional
from decimal import Decimal
from datetime import date, timedelta
from calendar import monthrange

from django.db import transaction
from django.utils import timezone

from .baseline_calculator import BaselineCalculator
from ..models import BudgetPlan, BudgetAllocation, BudgetPeriod
from transactions.utils import trace


def add_months(source_date: date, months: int) -> date:
    """Add months to a date, handling month/year overflow."""
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    day = min(source_date.day, monthrange(year, month)[1])
    return date(year, month, day)


class BudgetWizard:
    """Orchestrates the budget creation wizard flow."""

    def __init__(self, baseline_calculator: Optional[BaselineCalculator] = None):
        self.baseline_calculator = baseline_calculator or BaselineCalculator()

    @trace
    def generate_budget_draft(
        self,
        target_months: int = 3,
        method: str = "median",
        starting_year: Optional[int] = None,
        starting_month: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate initial budget draft based on historical data with month-specific calculations.

        Returns dict with:
        - budget_items: List of suggested budget entries (combined from all months)
        - periods: List of target periods with month-specific data
        - summary: Aggregate statistics
        """
        # Determine starting period
        if not starting_year or not starting_month:
            today = date.today()
            # Start with next month by default
            next_month = add_months(today, 1)
            starting_year = next_month.year
            starting_month = next_month.month

        # Generate target periods with month-specific suggestions
        periods = []
        all_suggestions_by_month = {}
        current_date = date(starting_year, starting_month, 1)

        for i in range(target_months):
            period_date = add_months(current_date, i)
            period_key = f"{period_date.year}_{period_date.month}"

            # Get payoree-based baseline suggestions (simplified)
            month_suggestions = self.baseline_calculator.get_payoree_suggestions(
                target_months=1,
                method=method,
            )

            all_suggestions_by_month[period_key] = month_suggestions

            periods.append(
                {
                    "year": period_date.year,
                    "month": period_date.month,
                    "display": period_date.strftime("%B %Y"),
                    "suggestions": month_suggestions,
                    "period_key": period_key,
                }
            )

        # For backward compatibility, also provide a combined list
        # Use the first month's suggestions as the base template
        first_period_suggestions = (
            list(all_suggestions_by_month.values())[0]
            if all_suggestions_by_month
            else []
        )

        # Calculate combined summary statistics
        total_baseline = 0
        total_suggested = 0
        for month_suggestions in all_suggestions_by_month.values():
            total_baseline += sum(item["baseline_amount"] for item in month_suggestions)
            total_suggested += sum(
                item["suggested_amount"] for item in month_suggestions
            )

        total_variance = total_suggested - total_baseline

        return {
            "budget_items": first_period_suggestions,  # For backward compatibility
            "periods": periods,
            "suggestions_by_month": all_suggestions_by_month,
            "summary": {
                "total_baseline": total_baseline,
                "total_suggested": total_suggested,
                "total_variance": total_variance,
                "variance_percentage": (
                    float((total_variance / total_baseline * 100))
                    if total_baseline
                    else 0
                ),
                "item_count": len(first_period_suggestions),
                "total_periods": target_months,
            },
            "method_used": method,
        }

    @trace
    def apply_ai_suggestions(
        self,
        draft_items: List[Dict],
        adjustment_preferences: Optional[Dict[str, float]] = None,
    ) -> List[Dict]:
        """
        Apply AI suggestions to budget draft items.

        Leverages existing categorization AI and applies smart adjustments
        based on needs levels and spending patterns.
        """
        if not adjustment_preferences:
            adjustment_preferences = {
                "critical": 1.05,  # 5% buffer for critical needs
                "core": 1.02,  # 2% buffer for core needs
                "lifestyle": 0.95,  # 5% reduction for lifestyle
                "discretionary": 0.90,  # 10% reduction for discretionary
                "luxury": 0.85,  # 15% reduction for luxury
                "deferred": 0.80,  # 20% reduction for deferred
            }

        enhanced_items = []

        for item in draft_items:
            # Apply needs-level based adjustment
            needs_level = item.get("needs_level")
            adjustment_factor = adjustment_preferences.get(needs_level, 1.0)

            # Calculate AI-enhanced suggestion
            baseline = item["baseline_amount"]
            ai_suggested = baseline * Decimal(str(adjustment_factor))

            # Round to nearest dollar for cleaner budgets
            ai_suggested = ai_suggested.quantize(Decimal("1"))

            # Add confidence score based on supporting data
            support = item.get("support", {})
            n_months = support.get("n_months", 0)
            n_transactions = support.get("total_transactions", 0)

            # Simple confidence scoring
            confidence = min(
                0.95, max(0.5, (n_months / 12.0) * (min(n_transactions, 50) / 50.0))
            )

            enhanced_item = item.copy()
            enhanced_item.update(
                {
                    "ai_suggested_amount": ai_suggested,
                    "adjustment_factor": adjustment_factor,
                    "confidence": confidence,
                    "ai_reasoning": self._generate_ai_reasoning(
                        item, adjustment_factor
                    ),
                }
            )

            enhanced_items.append(enhanced_item)

        return enhanced_items

    def _generate_ai_reasoning(self, item: Dict, adjustment_factor: float) -> str:
        """Generate human-readable reasoning for AI suggestions."""
        needs_level = item.get("needs_level", "unknown")
        support = item.get("support", {})
        n_months = support.get("n_months", 0)
        variance_pct = item.get("variance_pct", 0)

        reasoning_parts = []

        # Base data confidence
        if n_months >= 6:
            reasoning_parts.append(f"Based on {n_months} months of data")
        else:
            reasoning_parts.append(f"Limited data ({n_months} months)")

        # Adjustment reasoning
        if adjustment_factor > 1.0:
            pct = (adjustment_factor - 1.0) * 100
            reasoning_parts.append(f"+{pct:.0f}% buffer for {needs_level} needs")
        elif adjustment_factor < 1.0:
            pct = (1.0 - adjustment_factor) * 100
            reasoning_parts.append(
                f"-{pct:.0f}% reduction target for {needs_level} spending"
            )
        else:
            reasoning_parts.append("Baseline amount maintained")

        return ". ".join(reasoning_parts) + "."

    @trace
    def commit_budget_draft(
        self,
        budget_items: List[Dict] = None,
        target_periods: List[Dict] = None,
        suggestions_by_month: Optional[Dict[str, List[Dict]]] = None,
        overwrite_existing: bool = True,
    ) -> Dict[str, Any]:
        """
        Commit budget items to database for specified periods.

        Creates Budget and BudgetPeriod records, with optional overwrite of existing.
        Now supports month-specific suggestions for improved accuracy.

        Args:
            budget_items: Legacy format - list of budget items (for backward compatibility)
            target_periods: List of period dictionaries with year/month
            suggestions_by_month: Dict mapping period keys to month-specific suggestions
            overwrite_existing: Whether to overwrite existing budget records
        """
        created_budgets = []
        updated_budgets = []
        created_periods = []

        with transaction.atomic():
            for period in target_periods:
                year, month = period["year"], period["month"]
                period_key = f"{year}_{month}"

                # Create or get budget plan for this period (default to "Normal" plan)
                budget_plan, plan_created = BudgetPlan.objects.get_or_create(
                    name="Normal Budget",  # Default plan name
                    year=year,
                    month=month,
                    defaults={
                        "is_active": True,
                        "description": "Generated via Budget Wizard",
                    },
                )

                if plan_created:
                    created_periods.append(budget_plan)

                # Create legacy BudgetPeriod for backward compatibility
                budget_period, period_created = BudgetPeriod.objects.get_or_create(
                    year=year,
                    month=month,
                    defaults={"notes": f"Created via Budget Wizard"},
                )

                # Determine which budget items to use for this period
                if suggestions_by_month and period_key in suggestions_by_month:
                    # Use month-specific suggestions
                    period_items = suggestions_by_month[period_key]
                else:
                    # Fall back to generic budget items (backward compatibility)
                    period_items = budget_items or []

                # Process budget items for this period
                for item in period_items:
                    payoree_id = item.get("payoree_id")
                    if not payoree_id:
                        continue  # Skip items without payoree

                    allocation_data = {
                        "budget_plan": budget_plan,
                        "payoree_id": payoree_id,
                        "amount": item.get("suggested_amount")
                        or item.get("ai_suggested_amount"),
                        "baseline_amount": item.get("baseline_amount"),
                        "is_ai_suggested": True,
                        "user_note": f"Generated by Budget Wizard using {item.get('method_used', 'median')} method",
                    }

                    # Remove None values to avoid unique constraint issues
                    allocation_data = {
                        k: v for k, v in allocation_data.items() if v is not None
                    }

                    if overwrite_existing:
                        # Update or create budget allocation (simplified for payoree-centric model)
                        allocation, allocation_created = (
                            BudgetAllocation.objects.update_or_create(
                                budget_plan=budget_plan,
                                payoree_id=payoree_id,
                                defaults=allocation_data,
                            )
                        )

                        if allocation_created:
                            created_budgets.append(allocation)
                        else:
                            updated_budgets.append(allocation)
                    else:
                        # Only create if doesn't exist
                        try:
                            allocation = BudgetAllocation.objects.create(
                                **allocation_data
                            )
                            created_budgets.append(allocation)
                        except Exception:
                            # Allocation already exists, skip
                            pass

                # Update period totals
                budget_period.update_totals()

        return {
            "created_budgets": len(created_budgets),
            "updated_budgets": len(updated_budgets),
            "created_periods": len(created_periods),
            "periods_processed": len(target_periods),
            "success": True,
        }

    @trace
    def get_existing_budget_summary(
        self, year: int, month: int
    ) -> Optional[Dict[str, Any]]:
        """Get summary of existing budget allocations for a given period."""
        try:
            # Get budget plans for this period
            budget_plans = BudgetPlan.objects.filter(year=year, month=month)
            if not budget_plans.exists():
                return None

            # Get all allocations for this period
            allocations = BudgetAllocation.objects.filter(
                budget_plan__year=year, budget_plan__month=month
            ).select_related("budget_plan", "category", "subcategory", "payoree")

            # Get legacy period if it exists
            try:
                period = BudgetPeriod.objects.get(year=year, month=month)
            except BudgetPeriod.DoesNotExist:
                period = None

            total_budgeted = sum(a.amount for a in allocations)

            return {
                "period": period,
                "budget_plans": list(budget_plans),
                "allocation_count": len(allocations),
                "total_budgeted": total_budgeted,
                "baseline_total": sum(a.baseline_amount or 0 for a in allocations),
                "is_finalized": period.is_finalized if period else False,
                "allocations": list(allocations),
            }
        except BudgetPeriod.DoesNotExist:
            return None
