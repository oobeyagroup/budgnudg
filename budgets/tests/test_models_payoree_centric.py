"""
Tests for BudgetPlan and BudgetAllocation models.

Updated for payoree-centric budget refactoring.
Covers model validation, relationships, methods, and constraints.
"""

from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from budgets.models import BudgetPlan, BudgetAllocation
from transactions.models import Category, Payoree, RecurringSeries


class BudgetPlanModelTest(TestCase):
    """Test BudgetPlan model functionality."""

    def test_budget_plan_creation(self):
        """Test creating a budget plan."""
        plan = BudgetPlan.objects.create(
            name="October Budget",
            year=2025,
            month=10,
            is_active=True,
            description="Monthly budget for October",
        )

        self.assertEqual(plan.name, "October Budget")
        self.assertEqual(plan.year, 2025)
        self.assertEqual(plan.month, 10)
        self.assertTrue(plan.is_active)
        self.assertEqual(str(plan), "October Budget - 2025-10")

    def test_budget_plan_unique_constraint(self):
        """Test that name, year, month must be unique together."""
        BudgetPlan.objects.create(name="Budget", year=2025, month=10)

        with self.assertRaises(IntegrityError):
            BudgetPlan.objects.create(name="Budget", year=2025, month=10)

    def test_budget_plan_ordering(self):
        """Test that budget plans are ordered correctly."""
        plan1 = BudgetPlan.objects.create(name="A", year=2024, month=12)
        plan2 = BudgetPlan.objects.create(name="B", year=2025, month=1)
        plan3 = BudgetPlan.objects.create(name="C", year=2025, month=1)

        plans = list(BudgetPlan.objects.all())
        # Should be ordered by -year, -month, name
        self.assertEqual(plans[0], plan2)  # 2025-01 B
        self.assertEqual(plans[1], plan3)  # 2025-01 C
        self.assertEqual(plans[2], plan1)  # 2024-12 A


class BudgetAllocationModelTest(TestCase):
    """Test BudgetAllocation model functionality (payoree-centric)."""

    def setUp(self):
        """Set up test data."""
        self.category = Category.objects.create(name="Groceries", type="expense")
        self.subcategory = Category.objects.create(
            name="Organic Foods", parent=self.category, type="expense"
        )
        self.payoree = Payoree.objects.create(
            name="Whole Foods",
            default_category=self.category,
            default_subcategory=self.subcategory,
        )

        self.budget_plan = BudgetPlan.objects.create(
            name="Test Budget", year=2025, month=10, is_active=True
        )

    def test_allocation_creation_with_payoree(self):
        """Test creating budget allocation with payoree (simplified model)."""
        allocation = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan, payoree=self.payoree, amount=Decimal("500.00")
        )

        self.assertEqual(allocation.payoree, self.payoree)
        self.assertEqual(allocation.amount, Decimal("500.00"))
        self.assertEqual(allocation.budget_plan, self.budget_plan)
        self.assertTrue(allocation.is_active)

    def test_effective_category_properties(self):
        """Test effective category properties derive from payoree."""
        allocation = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan, payoree=self.payoree, amount=Decimal("200.00")
        )

        self.assertEqual(allocation.effective_category, self.category)
        self.assertEqual(allocation.effective_subcategory, self.subcategory)

    def test_allocation_with_ai_suggestion(self):
        """Test creating allocation with AI suggestion metadata."""
        allocation = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan,
            payoree=self.payoree,
            amount=Decimal("300.00"),
            is_ai_suggested=True,
            baseline_amount=Decimal("250.00"),
            user_note="AI suggested based on 6-month average",
        )

        self.assertTrue(allocation.is_ai_suggested)
        self.assertEqual(allocation.baseline_amount, Decimal("250.00"))
        self.assertEqual(allocation.user_note, "AI suggested based on 6-month average")

    def test_allocation_validation_missing_payoree(self):
        """Test validation fails when no payoree is provided."""
        allocation = BudgetAllocation(
            budget_plan=self.budget_plan,
            # payoree=None,  # Missing required payoree
            amount=Decimal("500.00"),
        )

        with self.assertRaises(ValidationError) as cm:
            allocation.full_clean()

        error_messages = str(cm.exception)
        self.assertIn("Payoree is required", error_messages)

    def test_allocation_unique_constraint(self):
        """Test that payoree can only have one allocation per budget plan."""
        # Create first allocation
        BudgetAllocation.objects.create(
            budget_plan=self.budget_plan, payoree=self.payoree, amount=Decimal("500.00")
        )

        # Try to create duplicate - should fail
        with self.assertRaises(IntegrityError):
            BudgetAllocation.objects.create(
                budget_plan=self.budget_plan,
                payoree=self.payoree,
                amount=Decimal("300.00"),
            )

    def test_allocation_properties(self):
        """Test allocation property methods."""
        allocation = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan,
            payoree=self.payoree,
            amount=Decimal("500.00"),
            baseline_amount=Decimal("450.00"),
        )

        # Test year/month properties
        self.assertEqual(allocation.year, 2025)
        self.assertEqual(allocation.month, 10)
        self.assertEqual(allocation.period_display, "October 2025")

        # Test variance calculations
        self.assertEqual(allocation.get_variance_vs_baseline(), Decimal("50.00"))
        variance_pct = allocation.get_variance_percentage()
        expected_pct = (
            (Decimal("500.00") - Decimal("450.00")) / Decimal("450.00")
        ) * 100
        self.assertAlmostEqual(float(variance_pct), float(expected_pct), places=2)

        # Test date properties
        self.assertEqual(allocation.start_date, date(2025, 10, 1))
        self.assertEqual(allocation.end_date, date(2025, 10, 31))

    def test_allocation_with_recurring_series(self):
        """Test allocation linked to recurring series."""
        recurring_series = RecurringSeries.objects.create(
            payoree=self.payoree,
            amount_cents=50000,  # $500.00 in cents
            interval="monthly",
        )

        allocation = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan,
            payoree=self.payoree,
            amount=Decimal("500.00"),
            recurring_series=recurring_series,
        )

        self.assertEqual(allocation.recurring_series, recurring_series)

    def test_str_representation(self):
        """Test string representation of allocation."""
        allocation = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan, payoree=self.payoree, amount=Decimal("500.00")
        )

        expected_str = f"{self.budget_plan.name}: {self.payoree.name} - $500.00"
        self.assertEqual(str(allocation), expected_str)

    def test_multiple_payorees_same_plan(self):
        """Test multiple payorees can have allocations in same plan."""
        payoree2 = Payoree.objects.create(
            name="Safeway", default_category=self.category
        )

        allocation1 = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan, payoree=self.payoree, amount=Decimal("300.00")
        )

        allocation2 = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan, payoree=payoree2, amount=Decimal("200.00")
        )

        self.assertNotEqual(allocation1.id, allocation2.id)
        self.assertEqual(allocation1.budget_plan, allocation2.budget_plan)
        self.assertNotEqual(allocation1.payoree, allocation2.payoree)

    def test_payoree_without_subcategory(self):
        """Test payoree with only category (no subcategory)."""
        utilities_category = Category.objects.create(name="Utilities", type="expense")
        electric_company = Payoree.objects.create(
            name="Electric Company",
            default_category=utilities_category,
            # No default_subcategory
        )

        allocation = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan,
            payoree=electric_company,
            amount=Decimal("150.00"),
        )

        self.assertEqual(allocation.effective_category, utilities_category)
        self.assertIsNone(allocation.effective_subcategory)

    def test_allocation_ordering(self):
        """Test that allocations are ordered by budget_plan then payoree name."""
        # Note: BudgetPlan ordering is ["-year", "-month", "name"]
        # So newer plans come first (2025-11 before 2025-10)
        plan2 = BudgetPlan.objects.create(name="Plan B", year=2025, month=11)

        payoree_b = Payoree.objects.create(
            name="B Store", default_category=self.category
        )
        payoree_z = Payoree.objects.create(
            name="Z Store", default_category=self.category
        )

        alloc1 = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan, payoree=payoree_z, amount=Decimal("100")
        )
        alloc2 = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan, payoree=payoree_b, amount=Decimal("200")
        )
        alloc3 = BudgetAllocation.objects.create(
            budget_plan=plan2, payoree=payoree_z, amount=Decimal("300")
        )

        allocations = list(BudgetAllocation.objects.all())

        # BudgetAllocation ordering is ["budget_plan", "payoree__name"]
        # But BudgetPlan has its own ordering which affects the FK ordering
        # Plan B (2025-11) comes before Test Budget (2025-10) due to BudgetPlan ordering
        self.assertEqual(allocations[0], alloc3)  # Plan B: Z Store (newer plan first)
        self.assertEqual(allocations[1], alloc2)  # Test Budget: B Store
        self.assertEqual(allocations[2], alloc1)  # Test Budget: Z Store
