"""
Tests for Budget and BudgetPeriod models.

Covers model validation, relationships, methods, and constraints.
"""

from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from budgets.models import Budget, BudgetPeriod
from transactions.models import Category, Payoree, RecurringSeries


class BudgetModelTest(TestCase):
    """Test Budget model functionality."""

    def setUp(self):
        """Set up test data."""
        self.category = Category.objects.create(name="Groceries", type="expense")
        self.subcategory = Category.objects.create(
            name="Organic Foods", parent=self.category, type="expense"
        )
        self.payoree = Payoree.objects.create(name="Whole Foods")

    def test_budget_creation_with_category(self):
        """Test creating budget with category."""
        budget = Budget.objects.create(
            category=self.category,
            amount=Decimal("500.00"),
            start_date=date(2025, 10, 1),
            end_date=date(2025, 12, 31),
            needs_level="Need",
        )

        self.assertEqual(budget.category, self.category)
        self.assertEqual(budget.amount, Decimal("500.00"))
        self.assertEqual(budget.needs_level, "Need")
        self.assertTrue(budget.is_active)

    def test_budget_creation_with_subcategory(self):
        """Test creating budget with subcategory."""
        budget = Budget.objects.create(
            category=self.category,
            subcategory=self.subcategory,
            amount=Decimal("200.00"),
            start_date=date(2025, 10, 1),
            end_date=date(2025, 12, 31),
            needs_level="Want",
        )

        self.assertEqual(budget.category, self.category)
        self.assertEqual(budget.subcategory, self.subcategory)
        self.assertEqual(budget.amount, Decimal("200.00"))

    def test_budget_creation_with_payoree(self):
        """Test creating budget with payoree."""
        budget = Budget.objects.create(
            payoree=self.payoree,
            amount=Decimal("300.00"),
            start_date=date(2025, 10, 1),
            end_date=date(2025, 12, 31),
            needs_level="Wish",
        )

        self.assertEqual(budget.payoree, self.payoree)
        self.assertEqual(budget.amount, Decimal("300.00"))

    def test_budget_creation_needs_level_only(self):
        """Test creating budget with only needs level."""
        budget = Budget.objects.create(
            amount=Decimal("1000.00"),
            start_date=date(2025, 10, 1),
            end_date=date(2025, 12, 31),
            needs_level="Need",
        )

        self.assertIsNone(budget.category)
        self.assertIsNone(budget.payoree)
        self.assertEqual(budget.needs_level, "Need")

    def test_budget_validation_empty_scope(self):
        """Test validation fails when no scope is defined."""
        with self.assertRaises(ValidationError) as cm:
            budget = Budget(
                amount=Decimal("500.00"),
                start_date=date(2025, 10, 1),
                end_date=date(2025, 12, 31),
                # No category, payoree, or needs_level
            )
            budget.full_clean()

        self.assertIn("At least one scope field must be specified", str(cm.exception))

    def test_budget_validation_invalid_date_range(self):
        """Test validation fails when end_date is before start_date."""
        with self.assertRaises(ValidationError) as cm:
            budget = Budget(
                category=self.category,
                amount=Decimal("500.00"),
                start_date=date(2025, 12, 31),
                end_date=date(2025, 10, 1),  # End before start
                needs_level="Need",
            )
            budget.full_clean()

        self.assertIn("End date must be after start date", str(cm.exception))

    def test_budget_validation_negative_amount(self):
        """Test validation fails for negative amounts."""
        with self.assertRaises(ValidationError) as cm:
            budget = Budget(
                category=self.category,
                amount=Decimal("-100.00"),  # Negative amount
                start_date=date(2025, 10, 1),
                end_date=date(2025, 12, 31),
                needs_level="Need",
            )
            budget.full_clean()

        self.assertIn("Amount must be greater than zero", str(cm.exception))

    def test_budget_validation_subcategory_without_category(self):
        """Test validation fails when subcategory is set without category."""
        with self.assertRaises(ValidationError) as cm:
            budget = Budget(
                subcategory=self.subcategory,  # No category
                amount=Decimal("200.00"),
                start_date=date(2025, 10, 1),
                end_date=date(2025, 12, 31),
                needs_level="Want",
            )
            budget.full_clean()

        self.assertIn("Subcategory cannot be set without a category", str(cm.exception))

    def test_budget_validation_invalid_needs_level(self):
        """Test validation fails for invalid needs level."""
        with self.assertRaises(ValidationError):
            Budget.objects.create(
                category=self.category,
                amount=Decimal("500.00"),
                start_date=date(2025, 10, 1),
                end_date=date(2025, 12, 31),
                needs_level="Invalid",  # Invalid choice
            )

    def test_budget_str_representation(self):
        """Test string representation of budgets."""
        # Category budget
        budget1 = Budget.objects.create(
            category=self.category,
            amount=Decimal("500.00"),
            start_date=date(2025, 10, 1),
            end_date=date(2025, 12, 31),
            needs_level="Need",
        )
        self.assertIn("Groceries", str(budget1))

        # Payoree budget
        budget2 = Budget.objects.create(
            payoree=self.payoree,
            amount=Decimal("300.00"),
            start_date=date(2025, 10, 1),
            end_date=date(2025, 12, 31),
            needs_level="Want",
        )
        self.assertIn("Whole Foods", str(budget2))

        # Needs level only budget
        budget3 = Budget.objects.create(
            amount=Decimal("1000.00"),
            start_date=date(2025, 10, 1),
            end_date=date(2025, 12, 31),
            needs_level="Need",
        )
        self.assertIn("Need", str(budget3))

    def test_budget_unique_constraints(self):
        """Test unique constraint enforcement."""
        # Create first budget
        Budget.objects.create(
            category=self.category,
            amount=Decimal("500.00"),
            start_date=date(2025, 10, 1),
            end_date=date(2025, 12, 31),
            needs_level="Need",
        )

        # Try to create duplicate budget (should fail)
        with self.assertRaises(IntegrityError):
            Budget.objects.create(
                category=self.category,
                amount=Decimal("600.00"),  # Different amount
                start_date=date(2025, 10, 1),
                end_date=date(2025, 12, 31),
                needs_level="Need",
            )


class BudgetPeriodModelTest(TestCase):
    """Test BudgetPeriod model functionality."""

    def setUp(self):
        """Set up test data."""
        self.category = Category.objects.create(
            name="Groceries", description="Food and household items"
        )

        self.budget = Budget.objects.create(
            category=self.category,
            amount=Decimal("600.00"),  # $200/month for 3 months
            start_date=date(2025, 10, 1),
            end_date=date(2025, 12, 31),
            needs_level="Need",
        )

    def test_budget_period_creation(self):
        """Test creating budget period."""
        period = BudgetPeriod.objects.create(
            budget=self.budget,
            period_year=2025,
            period_month=10,
            actual_spent=Decimal("180.50"),
        )

        self.assertEqual(period.budget, self.budget)
        self.assertEqual(period.period_year, 2025)
        self.assertEqual(period.period_month, 10)
        self.assertEqual(period.actual_spent, Decimal("180.50"))

    def test_budget_period_validation_invalid_month(self):
        """Test validation fails for invalid month."""
        with self.assertRaises(ValidationError) as cm:
            period = BudgetPeriod(
                budget=self.budget,
                period_year=2025,
                period_month=13,  # Invalid month
                actual_spent=Decimal("100.00"),
            )
            period.full_clean()

        self.assertIn("Month must be between 1 and 12", str(cm.exception))

    def test_budget_period_validation_negative_spent(self):
        """Test validation fails for negative spent amount."""
        with self.assertRaises(ValidationError) as cm:
            period = BudgetPeriod(
                budget=self.budget,
                period_year=2025,
                period_month=10,
                actual_spent=Decimal("-50.00"),  # Negative amount
            )
            period.full_clean()

        self.assertIn("Spent amount cannot be negative", str(cm.exception))

    def test_budget_period_str_representation(self):
        """Test string representation of budget periods."""
        period = BudgetPeriod.objects.create(
            budget=self.budget,
            period_year=2025,
            period_month=10,
            actual_spent=Decimal("180.50"),
        )

        str_repr = str(period)
        self.assertIn("2025-10", str_repr)
        self.assertIn("Groceries", str_repr)

    def test_budget_period_unique_constraint(self):
        """Test unique constraint per budget/period."""
        # Create first period
        BudgetPeriod.objects.create(
            budget=self.budget,
            period_year=2025,
            period_month=10,
            actual_spent=Decimal("180.50"),
        )

        # Try to create duplicate period (should fail)
        with self.assertRaises(IntegrityError):
            BudgetPeriod.objects.create(
                budget=self.budget,
                period_year=2025,
                period_month=10,  # Same period
                actual_spent=Decimal("200.00"),
            )

    def test_budget_period_ordering(self):
        """Test budget periods are ordered by period."""
        # Create periods out of order
        period2 = BudgetPeriod.objects.create(
            budget=self.budget,
            period_year=2025,
            period_month=11,
            actual_spent=Decimal("150.00"),
        )

        period1 = BudgetPeriod.objects.create(
            budget=self.budget,
            period_year=2025,
            period_month=10,
            actual_spent=Decimal("180.50"),
        )

        period3 = BudgetPeriod.objects.create(
            budget=self.budget,
            period_year=2025,
            period_month=12,
            actual_spent=Decimal("200.00"),
        )

        # Check they're returned in chronological order
        periods = list(BudgetPeriod.objects.all())
        self.assertEqual(periods[0], period1)  # October
        self.assertEqual(periods[1], period2)  # November
        self.assertEqual(periods[2], period3)  # December


class BudgetModelMethodsTest(TestCase):
    """Test Budget model methods and properties."""

    def setUp(self):
        """Set up test data."""
        self.category = Category.objects.create(
            name="Groceries", description="Food and household items"
        )

        # 3-month budget: Oct-Dec 2025
        self.budget = Budget.objects.create(
            category=self.category,
            amount=Decimal("600.00"),  # $200/month
            start_date=date(2025, 10, 1),
            end_date=date(2025, 12, 31),
            needs_level="Need",
        )

        # Add some period data
        BudgetPeriod.objects.create(
            budget=self.budget,
            period_year=2025,
            period_month=10,
            actual_spent=Decimal("180.50"),
        )

        BudgetPeriod.objects.create(
            budget=self.budget,
            period_year=2025,
            period_month=11,
            actual_spent=Decimal("220.75"),  # Over budget this month
        )

    def test_get_duration_months(self):
        """Test calculating budget duration in months."""
        duration = self.budget.get_duration_months()
        self.assertEqual(duration, 3)

        # Test single month budget
        single_month_budget = Budget.objects.create(
            category=self.category,
            amount=Decimal("200.00"),
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 31),
            needs_level="Need",
        )
        self.assertEqual(single_month_budget.get_duration_months(), 1)

    def test_get_monthly_budget_amount(self):
        """Test calculating monthly budget amount."""
        monthly_amount = self.budget.get_monthly_budget_amount()
        self.assertEqual(monthly_amount, Decimal("200.00"))  # 600/3

    def test_get_total_spent(self):
        """Test calculating total spent across all periods."""
        total_spent = self.budget.get_total_spent()
        expected = Decimal("180.50") + Decimal("220.75")
        self.assertEqual(total_spent, expected)

    def test_get_remaining_amount(self):
        """Test calculating remaining budget amount."""
        remaining = self.budget.get_remaining_amount()
        spent = Decimal("180.50") + Decimal("220.75")  # 401.25
        expected = Decimal("600.00") - spent  # 198.75
        self.assertEqual(remaining, expected)

    def test_get_spent_percentage(self):
        """Test calculating spent percentage."""
        percentage = self.budget.get_spent_percentage()
        spent = Decimal("180.50") + Decimal("220.75")  # 401.25
        expected = (spent / Decimal("600.00")) * 100  # ~66.875%
        self.assertAlmostEqual(float(percentage), float(expected), places=2)

    def test_is_over_budget(self):
        """Test checking if budget is over spent."""
        # Current budget should not be over (401.25 < 600.00)
        self.assertFalse(self.budget.is_over_budget())

        # Add more spending to put it over
        BudgetPeriod.objects.create(
            budget=self.budget,
            period_year=2025,
            period_month=12,
            actual_spent=Decimal("250.00"),  # This will put total over 600
        )

        # Refresh from database
        self.budget.refresh_from_db()
        self.assertTrue(self.budget.is_over_budget())

    def test_is_active_property(self):
        """Test is_active property based on dates."""
        # Create budget for past period
        past_budget = Budget.objects.create(
            category=self.category,
            amount=Decimal("300.00"),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            needs_level="Need",
        )

        # Create budget for future period
        future_budget = Budget.objects.create(
            category=self.category,
            amount=Decimal("400.00"),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            needs_level="Need",
        )

        # Test active status
        # Note: These tests assume current date context from test environment
        # In real implementation, you might want to mock date.today()
        self.assertFalse(past_budget.is_active)
        # Future budget activeness depends on current test date
