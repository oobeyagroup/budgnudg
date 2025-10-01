"""
Budget Allocation Deletion Service

This service handles the safe deletion of budget allocations with proper
impact analysis, data preservation, and user feedback. It implements the
acceptance criteria defined in delete_budget_allocations.md.
"""

from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError

from budgets.models import BudgetAllocation, BudgetPlan
from transactions.models import Transaction, Payoree


class AllocationDeletionError(Exception):
    """Custom exception for allocation deletion errors."""

    pass


class AllocationDeletionService:
    """Service for handling budget allocation deletion operations."""

    def analyze_deletion_impact(self, allocation: BudgetAllocation) -> Dict:
        """
        Analyze the impact of deleting a budget allocation.

        Returns:
            Dict with impact analysis including transaction count, spending totals,
            and recommendations for user consideration.
        """
        payoree = allocation.payoree
        budget_plan = allocation.budget_plan

        # Find related transactions for the payoree
        related_transactions = Transaction.objects.filter(payoree=payoree)

        # Separate transactions by time period
        period_transactions = related_transactions.filter(
            date__gte=budget_plan.start_date, date__lte=budget_plan.end_date
        )

        historical_transactions = related_transactions.filter(
            date__lt=budget_plan.start_date
        )

        # Calculate impact metrics
        period_count = period_transactions.count()
        historical_count = historical_transactions.count()
        total_count = related_transactions.count()

        period_spending = sum(abs(t.amount) for t in period_transactions)
        historical_spending = sum(abs(t.amount) for t in historical_transactions)
        total_spending = sum(abs(t.amount) for t in related_transactions)

        # Budget impact
        budget_total_before = sum(
            alloc.amount for alloc in budget_plan.allocations.all()
        )
        budget_total_after = budget_total_before - allocation.amount
        budget_impact_percentage = (
            (allocation.amount / budget_total_before) * 100
            if budget_total_before != 0
            else 0
        )

        return {
            "allocation_amount": allocation.amount,
            "payoree_name": payoree.name,
            "budget_plan_name": budget_plan.name,
            "transactions": {
                "current_period": period_count,
                "historical": historical_count,
                "total": total_count,
            },
            "spending": {
                "current_period": period_spending,
                "historical": historical_spending,
                "total": total_spending,
            },
            "budget_impact": {
                "amount": allocation.amount,
                "percentage": budget_impact_percentage,
                "total_before": budget_total_before,
                "total_after": budget_total_after,
            },
            "warnings": self._generate_deletion_warnings(
                allocation, period_count, historical_count
            ),
            "recommendations": self._generate_deletion_recommendations(
                allocation, period_spending, historical_spending
            ),
        }

    def _generate_deletion_warnings(
        self, allocation: BudgetAllocation, period_count: int, historical_count: int
    ) -> List[str]:
        """Generate warnings for potential deletion issues."""
        warnings = []

        if period_count > 0:
            warnings.append(
                f"This payoree has {period_count} transactions in the current budget period"
            )

        if historical_count > 10:
            warnings.append(
                f"This payoree has extensive transaction history ({historical_count} transactions)"
            )

        if allocation.is_ai_suggested and allocation.baseline_amount:
            warnings.append("This allocation was AI-suggested based on historical data")

        if allocation.recurring_series:
            warnings.append("This allocation is linked to recurring transactions")

        return warnings

    def _generate_deletion_recommendations(
        self,
        allocation: BudgetAllocation,
        period_spending: Decimal,
        historical_spending: Decimal,
    ) -> List[str]:
        """Generate recommendations based on deletion impact."""
        recommendations = []

        if period_spending > allocation.amount:
            recommendations.append(
                f"Current spending (${period_spending}) exceeds allocation (${allocation.amount}). "
                "Consider if this payoree needs budget coverage elsewhere."
            )

        if historical_spending > 0 and allocation.amount == 0:
            recommendations.append(
                "This payoree has historical spending but zero allocation. "
                "Deletion may be appropriate for cleanup."
            )

        if allocation.is_ai_suggested and not allocation.user_note:
            recommendations.append(
                "Consider reviewing AI suggestion accuracy before deleting"
            )

        return recommendations

    def validate_deletion(self, allocation: BudgetAllocation) -> Tuple[bool, List[str]]:
        """
        Validate that an allocation can be safely deleted.

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check if allocation exists and is accessible
        if not allocation.pk:
            errors.append("Allocation does not exist")
            return False, errors

        # Check if budget plan is in a state that allows deletion
        if not allocation.budget_plan.is_active:
            errors.append("Cannot delete allocations from inactive budget plans")

        # Check for critical dependencies (extend as needed)
        # For now, no critical blocking conditions

        return len(errors) == 0, errors

    @transaction.atomic
    def delete_allocation(
        self, allocation: BudgetAllocation, force: bool = False
    ) -> Dict:
        """
        Delete a budget allocation with proper validation and impact tracking.

        Args:
            allocation: The BudgetAllocation to delete
            force: If True, bypass non-critical validation (use carefully)

        Returns:
            Dict with deletion results and impact information
        """
        # Validate deletion is allowed
        is_valid, errors = self.validate_deletion(allocation)
        if not is_valid and not force:
            raise AllocationDeletionError(
                f"Cannot delete allocation: {', '.join(errors)}"
            )

        # Get impact analysis before deletion
        impact_analysis = self.analyze_deletion_impact(allocation)

        # Store deletion metadata
        deletion_info = {
            "deleted_allocation": {
                "id": allocation.pk,
                "payoree_name": allocation.payoree.name,
                "amount": allocation.amount,
                "budget_plan": allocation.budget_plan.name,
                "was_ai_suggested": allocation.is_ai_suggested,
                "had_recurring_series": bool(allocation.recurring_series),
            },
            "impact_analysis": impact_analysis,
            "deletion_timestamp": None,  # Will be set after deletion
        }

        # Perform the deletion
        try:
            allocation.delete()
            deletion_info["success"] = True
            deletion_info["deletion_timestamp"] = (
                "immediate"  # In real app, use timezone.now()
            )

        except Exception as e:
            raise AllocationDeletionError(f"Database error during deletion: {str(e)}")

        return deletion_info

    @transaction.atomic
    def bulk_delete_allocations(
        self, allocations: List[BudgetAllocation], force: bool = False
    ) -> Dict:
        """
        Delete multiple allocations in a single transaction.

        Args:
            allocations: List of BudgetAllocation objects to delete
            force: If True, bypass non-critical validation

        Returns:
            Dict with bulk deletion results
        """
        if not allocations:
            return {"success": True, "deleted_count": 0, "errors": []}

        # Validate all allocations first
        all_valid = True
        validation_errors = []

        for i, allocation in enumerate(allocations):
            is_valid, errors = self.validate_deletion(allocation)
            if not is_valid:
                all_valid = False
                validation_errors.extend(
                    [f"Allocation {i+1}: {error}" for error in errors]
                )

        if not all_valid and not force:
            raise AllocationDeletionError(
                f"Bulk deletion validation failed: {'; '.join(validation_errors)}"
            )

        # Get combined impact analysis
        total_amount = sum(alloc.amount for alloc in allocations)
        payoree_names = [alloc.payoree.name for alloc in allocations]

        # Perform bulk deletion
        deleted_ids = [alloc.pk for alloc in allocations]

        try:
            # Delete all allocations
            for allocation in allocations:
                allocation.delete()

            return {
                "success": True,
                "deleted_count": len(allocations),
                "deleted_ids": deleted_ids,
                "total_amount": total_amount,
                "payoree_names": payoree_names,
                "errors": [],
            }

        except Exception as e:
            raise AllocationDeletionError(f"Bulk deletion failed: {str(e)}")

    def get_deletion_confirmation_data(self, allocation: BudgetAllocation) -> Dict:
        """
        Get data for deletion confirmation dialog.

        Returns formatted data for UI confirmation display.
        """
        impact = self.analyze_deletion_impact(allocation)

        return {
            "allocation": {
                "payoree_name": allocation.payoree.name,
                "amount": allocation.amount,
                "budget_plan": allocation.budget_plan.name,
                "is_ai_suggested": allocation.is_ai_suggested,
            },
            "impact_summary": {
                "transaction_count": impact["transactions"]["total"],
                "spending_total": impact["spending"]["total"],
                "budget_percentage": impact["budget_impact"]["percentage"],
            },
            "warnings": impact["warnings"],
            "recommendations": impact["recommendations"],
            "requires_confirmation": True,
        }
