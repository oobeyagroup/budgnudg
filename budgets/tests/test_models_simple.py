"""
Simplified tests for Budget models.

Tests the actual Budget and BudgetPeriod models as implemented.
"""

from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError

from budgets.models import Budget, BudgetPeriod
from transactions.models import Category, Payoree


class BudgetBasicTest(TestCase):
    """Basic tests for Budget model functionality."""

    def setUp(self):
        """Set up test data."""
        self.category = Category.objects.create(name="Groceries", type="expense")
        self.payoree = Payoree.objects.create(name="Whole Foods")

    def test_budget_creation_with_category(self):
        """Test creating budget with category."""
        budget = Budget.objects.create(
            category=self.category,
            year=2025,
            month=10,
            amount=Decimal("500.00"),
            needs_level="core",
        )

        self.assertEqual(budget.category, self.category)
        self.assertEqual(budget.year, 2025)
        self.assertEqual(budget.month, 10)
        self.assertEqual(budget.amount, Decimal("500.00"))
        self.assertEqual(budget.needs_level, "core")

    def test_budget_creation_with_payoree(self):
        """Test creating budget with payoree."""
        budget = Budget.objects.create(
            payoree=self.payoree,
            year=2025,
            month=10,
            amount=Decimal("300.00"),
            needs_level="lifestyle",
        )

        self.assertEqual(budget.payoree, self.payoree)
        self.assertEqual(budget.amount, Decimal("300.00"))

    def test_budget_str_representation(self):
        """Test string representation."""
        budget = Budget.objects.create(
            category=self.category,
            year=2025,
            month=10,
            amount=Decimal("500.00"),
            needs_level="core",
        )

        str_repr = str(budget)
        self.assertIn("Groceries", str_repr)
        self.assertIn("2025", str_repr)


class BudgetPeriodBasicTest(TestCase):
    """Basic tests for BudgetPeriod model functionality."""

    def setUp(self):
        """Set up test data."""
        self.category = Category.objects.create(name="Groceries", type="expense")

        self.budget = Budget.objects.create(
            category=self.category,
            year=2025,
            month=10,
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


class BudgetValidationTest(TestCase):
    """Test Budget model validation."""

    def setUp(self):
        """Set up test data."""
        self.category = Category.objects.create(name="Groceries", type="expense")

    def test_budget_validation_invalid_month(self):
        """Test validation fails for invalid month."""
        with self.assertRaises(ValidationError):
            budget = Budget(
                category=self.category,
                year=2025,
                month=13,  # Invalid month
                amount=Decimal("500.00"),
                needs_level="core",
            )
            budget.full_clean()

    def test_budget_validation_negative_amount(self):
        """Test validation fails for negative amounts."""
        with self.assertRaises(ValidationError):
            budget = Budget(
                category=self.category,
                year=2025,
                month=10,
                amount=Decimal("-100.00"),  # Negative amount
                needs_level="core",
            )
            budget.full_clean()
