"""
Tests for AllocationDeletionService

This tests the deletion service implementation against the ATDD criteria.
"""

from django.test import TestCase
from decimal import Decimal
from datetime import date, timedelta

from budgets.models import BudgetPlan, BudgetAllocation
from budgets.services.allocation_deletion import (
    AllocationDeletionService,
    AllocationDeletionError,
)
from transactions.models import Category, Payoree, Transaction


class TestAllocationDeletionService(TestCase):
    """Test the AllocationDeletionService functionality."""

    def setUp(self):
        """Set up test data."""
        # Create test categories
        self.groceries_category = Category.objects.create(
            name="Groceries", type="expense"
        )

        # Create test payorees
        self.grocery_store = Payoree.objects.create(
            name="Test Grocery Store",
            default_category=self.groceries_category,
        )

        # Create test budget plan
        self.budget_plan = BudgetPlan.objects.create(
            name="Test Budget", year=2025, month=10, is_active=True
        )

        # Create test allocation
        self.allocation = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan,
            payoree=self.grocery_store,
            amount=Decimal("500.00"),
            is_ai_suggested=True,
        )

        # Create test transactions
        base_date = date(2025, 10, 15)
        for i in range(3):
            Transaction.objects.create(
                source="test.csv",
                sheet_account="checking",
                account_type="checking",
                date=base_date - timedelta(days=i * 7),
                amount=Decimal("-75.00"),
                description=f"Test transaction {i+1}",
                payoree=self.grocery_store,
                category=self.groceries_category,
            )

        self.service = AllocationDeletionService()

    def test_analyze_deletion_impact(self):
        """Test impact analysis functionality."""
        impact = self.service.analyze_deletion_impact(self.allocation)

        # Check impact structure
        self.assertIn("allocation_amount", impact)
        self.assertIn("payoree_name", impact)
        self.assertIn("transactions", impact)
        self.assertIn("spending", impact)
        self.assertIn("budget_impact", impact)

        # Check transaction counts
        self.assertEqual(impact["transactions"]["current_period"], 3)
        self.assertEqual(impact["transactions"]["total"], 3)

        # Check spending totals
        expected_spending = Decimal("225.00")  # 3 * 75.00
        self.assertEqual(impact["spending"]["total"], expected_spending)

        # Check budget impact
        self.assertEqual(impact["budget_impact"]["amount"], Decimal("500.00"))

    def test_validate_deletion_success(self):
        """Test successful validation."""
        is_valid, errors = self.service.validate_deletion(self.allocation)

        self.assertTrue(is_valid)
        self.assertEqual(errors, [])

    def test_validate_deletion_inactive_budget(self):
        """Test validation with inactive budget."""
        self.budget_plan.is_active = False
        self.budget_plan.save()

        is_valid, errors = self.service.validate_deletion(self.allocation)

        self.assertFalse(is_valid)
        self.assertIn("inactive budget", errors[0])

    def test_delete_allocation_success(self):
        """Test successful allocation deletion."""
        initial_count = BudgetAllocation.objects.count()

        result = self.service.delete_allocation(self.allocation)

        # Check result structure
        self.assertTrue(result["success"])
        self.assertIn("deleted_allocation", result)
        self.assertIn("impact_analysis", result)

        # Verify deletion
        self.assertEqual(BudgetAllocation.objects.count(), initial_count - 1)
        self.assertFalse(
            BudgetAllocation.objects.filter(pk=self.allocation.pk).exists()
        )

        # Verify transactions are preserved
        self.assertEqual(
            Transaction.objects.filter(payoree=self.grocery_store).count(), 3
        )

    def test_delete_allocation_validation_error(self):
        """Test deletion with validation errors."""
        self.budget_plan.is_active = False
        self.budget_plan.save()

        with self.assertRaises(AllocationDeletionError):
            self.service.delete_allocation(self.allocation)

        # Allocation should still exist
        self.assertTrue(BudgetAllocation.objects.filter(pk=self.allocation.pk).exists())

    def test_bulk_delete_allocations(self):
        """Test bulk deletion functionality."""
        # Create additional payoree and allocation
        utilities_category = Category.objects.create(name="Utilities", type="expense")
        utility_company = Payoree.objects.create(
            name="Electric Company",
            default_category=utilities_category,
        )
        allocation2 = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan,
            payoree=utility_company,
            amount=Decimal("300.00"),
            is_ai_suggested=False,
        )

        allocations = [self.allocation, allocation2]
        initial_count = BudgetAllocation.objects.count()

        result = self.service.bulk_delete_allocations(allocations)

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["deleted_count"], 2)
        self.assertEqual(result["total_amount"], Decimal("800.00"))

        # Verify deletions
        self.assertEqual(BudgetAllocation.objects.count(), initial_count - 2)

    def test_get_deletion_confirmation_data(self):
        """Test confirmation data generation."""
        data = self.service.get_deletion_confirmation_data(self.allocation)

        # Check data structure
        self.assertIn("allocation", data)
        self.assertIn("impact_summary", data)
        self.assertIn("warnings", data)
        self.assertIn("recommendations", data)

        # Check allocation data
        self.assertEqual(data["allocation"]["payoree_name"], "Test Grocery Store")
        self.assertEqual(data["allocation"]["amount"], Decimal("500.00"))

        # Check impact summary
        self.assertEqual(data["impact_summary"]["transaction_count"], 3)
        self.assertEqual(data["impact_summary"]["spending_total"], Decimal("225.00"))

        # Should require confirmation
        self.assertTrue(data["requires_confirmation"])
