"""
Simplified tests for Budget models.

Tests the actual BudgetPlan, BudgetAllocation and BudgetPeriod models as implemented.
"""

from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError

from budgets.models import BudgetPlan, BudgetAllocation, BudgetPeriod
from transactions.models import Category, Payoree


class BudgetAllocationBasicTest(TestCase):
    """Basic tests for BudgetAllocation model functionality."""

    def setUp(self):
        """Set up test data."""
        self.category = Category.objects.create(name="Groceries", type="expense")
        self.payoree = Payoree.objects.create(name="Whole Foods")
        
        # Create a budget plan for allocations
        self.budget_plan = BudgetPlan.objects.create(
            name="Normal Budget",
            year=2025,
            month=10,
            is_active=True
        )

    def test_budget_allocation_creation_with_category(self):
        """Test creating budget allocation with category."""
        allocation = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan,
            category=self.category,
            amount=Decimal("500.00"),
            needs_level="core",
        )

        self.assertEqual(allocation.category, self.category)
        self.assertEqual(allocation.year, 2025)  # From budget_plan property
        self.assertEqual(allocation.month, 10)   # From budget_plan property
        self.assertEqual(allocation.amount, Decimal("500.00"))
        self.assertEqual(allocation.needs_level, "core")

    def test_budget_allocation_creation_with_payoree(self):
        """Test creating budget allocation with payoree."""
        allocation = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan,
            payoree=self.payoree,
            amount=Decimal("300.00"),
            needs_level="lifestyle",
        )

        self.assertEqual(allocation.payoree, self.payoree)
        self.assertEqual(allocation.amount, Decimal("300.00"))

    def test_budget_allocation_str_representation(self):
        """Test string representation."""
        allocation = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan,
            category=self.category,
            amount=Decimal("500.00"),
            needs_level="core",
        )

        str_repr = str(allocation)
        self.assertIn("Groceries", str_repr)
        self.assertIn("Normal Budget", str_repr)


class BudgetPlanBasicTest(TestCase):
    """Basic tests for BudgetPlan model functionality."""

    def setUp(self):
        """Set up test data.""" 
        self.category = Category.objects.create(name="Groceries", type="expense")

    def test_budget_plan_creation(self):
        """Test creating budget plan."""
        plan = BudgetPlan.objects.create(
            name="Normal Budget",
            year=2025,
            month=10,
            is_active=True,
            description="Test budget plan"
        )

        self.assertEqual(plan.name, "Normal Budget")
        self.assertEqual(plan.year, 2025)
        self.assertEqual(plan.month, 10)
        self.assertTrue(plan.is_active)


class BudgetPeriodBasicTest(TestCase):
    """Basic tests for BudgetPeriod model functionality."""

    def setUp(self):
        """Set up test data."""
        self.category = Category.objects.create(name="Groceries", type="expense")

        # Create budget plan and allocation for testing period updates
        self.budget_plan = BudgetPlan.objects.create(
            name="Normal Budget",
            year=2025,
            month=10,
            is_active=True
        )
        
        self.allocation = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan,
            category=self.category,
            amount=Decimal("500.00"),
            needs_level="core",
        )

    def test_budget_period_creation(self):
        """Test creating budget period."""
        period = BudgetPeriod.objects.create(
            year=2025,
            month=10,
            total_budgeted=Decimal("1000.00"),
            baseline_total=Decimal("950.00"),
        )

        self.assertEqual(period.year, 2025)
        self.assertEqual(period.month, 10)
        self.assertEqual(period.total_budgeted, Decimal("1000.00"))
        self.assertEqual(period.baseline_total, Decimal("950.00"))

    def test_budget_period_str_representation(self):
        """Test string representation."""
        period = BudgetPeriod.objects.create(
            year=2025, month=10, total_budgeted=Decimal("1000.00")
        )

        str_repr = str(period)
        self.assertIn("October", str_repr)
        self.assertIn("2025", str_repr)


class BudgetAllocationValidationTest(TestCase):
    """Test BudgetAllocation model validation."""

    def setUp(self):
        """Set up test data."""
        self.category = Category.objects.create(name="Groceries", type="expense")
        self.budget_plan = BudgetPlan.objects.create(
            name="Normal Budget",
            year=2025,
            month=10,
            is_active=True
        )

    def test_budget_plan_validation_invalid_month(self):
        """Test validation fails for invalid month."""
        with self.assertRaises(ValidationError):
            budget_plan = BudgetPlan(
                name="Test Budget",
                year=2025,
                month=13,  # Invalid month
            )
            budget_plan.full_clean()

    def test_budget_allocation_validation_no_scope(self):
        """Test validation fails when no scope is specified."""
        with self.assertRaises(ValidationError):
            allocation = BudgetAllocation(
                budget_plan=self.budget_plan,
                amount=Decimal("100.00"),
                # No category, subcategory, payoree, or needs_level
            )
            allocation.full_clean()

    def test_budget_allocation_allows_negative_amounts(self):
        """Test that negative amounts are now allowed (for expenses)."""
        allocation = BudgetAllocation(
            budget_plan=self.budget_plan,
            category=self.category,
            amount=Decimal("-100.00"),  # Negative amount (expense)
            needs_level="core",
        )
        # Should not raise ValidationError
        allocation.full_clean()
        allocation.save()
        self.assertEqual(allocation.amount, Decimal("-100.00"))
