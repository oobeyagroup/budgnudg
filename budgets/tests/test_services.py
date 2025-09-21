"""
Tests for budget service classes.

Covers BaselineCalculator and BudgetWizard functionality.
"""

from decimal import Decimal
from datetime import date
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone

from budgets.services.baseline_calculator import BaselineCalculator
from budgets.services.budget_wizard import BudgetWizard, add_months
from budgets.models import Budget, BudgetPeriod
from transactions.models import Transaction, Category, Payoree
from ingest.models import FinancialAccount


class BaselineCalculatorTest(TestCase):
    """Test BaselineCalculator service."""

    def setUp(self):
        """Set up test data."""
        self.category = Category.objects.create(name="Groceries", type="expense")
        self.subcategory = Category.objects.create(
            name="Organic Foods", parent=self.category, type="expense"
        )
        self.payoree = Payoree.objects.create(name="Whole Foods")
        self.account = FinancialAccount.objects.create(
            name="Test Checking Account",
            column_map={},
            description="Test checking account",
        )

        # Create sample transactions for the last 6 months
        self.create_sample_transactions()
        self.calculator = BaselineCalculator()

    def create_sample_transactions(self):
        """Create sample transaction data for testing."""
        transactions = [
            # Groceries - regular pattern
            {
                "date": date(2025, 4, 15),
                "amount": 120.50,
                "category": self.category,
                "payoree": self.payoree,
                "needs": "Need",
            },
            {
                "date": date(2025, 5, 15),
                "amount": 135.75,
                "category": self.category,
                "payoree": self.payoree,
                "needs": "Need",
            },
            {
                "date": date(2025, 6, 15),
                "amount": 110.25,
                "category": self.category,
                "payoree": self.payoree,
                "needs": "Need",
            },
            {
                "date": date(2025, 7, 15),
                "amount": 145.00,
                "category": self.category,
                "payoree": self.payoree,
                "needs": "Need",
            },
            {
                "date": date(2025, 8, 15),
                "amount": 128.80,
                "category": self.category,
                "payoree": self.payoree,
                "needs": "Need",
            },
            # Organic foods subcategory
            {
                "date": date(2025, 6, 10),
                "amount": 45.60,
                "category": self.category,
                "subcategory": self.subcategory,
                "payoree": self.payoree,
                "needs": "Want",
            },
            {
                "date": date(2025, 7, 10),
                "amount": 52.30,
                "category": self.category,
                "subcategory": self.subcategory,
                "payoree": self.payoree,
                "needs": "Want",
            },
            {
                "date": date(2025, 8, 10),
                "amount": 48.90,
                "category": self.category,
                "subcategory": self.subcategory,
                "payoree": self.payoree,
                "needs": "Want",
            },
        ]

        for tx_data in transactions:
            Transaction.objects.create(
                transaction_date=tx_data["date"],
                amount=Decimal(str(tx_data["amount"])),
                description=f"Purchase at {tx_data['payoree'].name}",
                bank_account=self.account,
                category=tx_data["category"],
                subcategory=tx_data.get("subcategory"),
                payoree=tx_data["payoree"],
                needs_level=tx_data["needs"],
                debit_credit="Debit",
            )

    def test_get_baseline_spending_category(self):
        """Test baseline calculation for category."""
        baseline = self.calculator.get_baseline_spending(
            category=self.category, months_back=6, method="median"
        )

        # Should find the grocery transactions
        self.assertGreater(baseline, Decimal("100.00"))
        self.assertLess(baseline, Decimal("200.00"))

    def test_get_baseline_spending_subcategory(self):
        """Test baseline calculation for subcategory."""
        baseline = self.calculator.get_baseline_spending(
            category=self.category,
            subcategory=self.subcategory,
            months_back=6,
            method="median",
        )

        # Should find the organic foods transactions
        self.assertGreater(baseline, Decimal("40.00"))
        self.assertLess(baseline, Decimal("60.00"))

    def test_get_baseline_spending_payoree(self):
        """Test baseline calculation for payoree."""
        baseline = self.calculator.get_baseline_spending(
            payoree=self.payoree, months_back=6, method="median"
        )

        # Should find all Whole Foods transactions
        self.assertGreater(baseline, Decimal("150.00"))  # Both categories combined

    def test_get_baseline_spending_needs_level(self):
        """Test baseline calculation for needs level."""
        baseline = self.calculator.get_baseline_spending(
            needs_level="Need", months_back=6, method="median"
        )

        # Should find all Need-level transactions
        self.assertGreater(baseline, Decimal("100.00"))

    def test_get_baseline_spending_methods(self):
        """Test different calculation methods."""
        # Test with same parameters but different methods
        median_baseline = self.calculator.get_baseline_spending(
            category=self.category, months_back=6, method="median"
        )

        mean_baseline = self.calculator.get_baseline_spending(
            category=self.category, months_back=6, method="mean"
        )

        max_baseline = self.calculator.get_baseline_spending(
            category=self.category, months_back=6, method="max"
        )

        # Max should be highest
        self.assertGreaterEqual(max_baseline, median_baseline)
        self.assertGreaterEqual(max_baseline, mean_baseline)

    def test_get_baseline_spending_no_data(self):
        """Test baseline calculation with no matching data."""
        other_category = Category.objects.create(
            name="Entertainment", description="Fun stuff"
        )

        baseline = self.calculator.get_baseline_spending(
            category=other_category, months_back=6, method="median"
        )

        self.assertEqual(baseline, Decimal("0.00"))

    def test_get_category_suggestions(self):
        """Test getting category suggestions."""
        suggestions = self.calculator.get_category_suggestions(
            target_months=3, method="median"
        )

        # Should return list of suggestion dictionaries
        self.assertIsInstance(suggestions, list)
        self.assertGreater(len(suggestions), 0)

        # Check suggestion structure
        for suggestion in suggestions:
            self.assertIn("category_id", suggestion)
            self.assertIn("baseline_amount", suggestion)
            self.assertIn("suggested_amount", suggestion)
            self.assertIsInstance(suggestion["baseline_amount"], Decimal)
            self.assertIsInstance(suggestion["suggested_amount"], Decimal)


class BudgetWizardTest(TestCase):
    """Test BudgetWizard service."""

    def setUp(self):
        """Set up test data."""
        self.category = Category.objects.create(
            name="Groceries", description="Food and household items"
        )

        # Mock the baseline calculator
        self.mock_calculator = MagicMock()
        self.wizard = BudgetWizard(baseline_calculator=self.mock_calculator)

    def test_add_months_utility(self):
        """Test the add_months utility function."""
        start_date = date(2025, 10, 15)

        # Add one month
        result = add_months(start_date, 1)
        self.assertEqual(result, date(2025, 11, 15))

        # Add multiple months
        result = add_months(start_date, 3)
        self.assertEqual(result, date(2026, 1, 15))

        # Handle month overflow
        result = add_months(date(2025, 1, 31), 1)
        # Should handle February not having 31 days
        self.assertEqual(result.month, 2)
        self.assertEqual(result.year, 2025)

        # Subtract months
        result = add_months(start_date, -2)
        self.assertEqual(result, date(2025, 8, 15))

    def test_generate_budget_draft(self):
        """Test generating budget draft."""
        # Mock baseline calculator response
        self.mock_calculator.get_category_suggestions.return_value = [
            {
                "category_id": self.category.id,
                "category_name": "Groceries",
                "subcategory_id": None,
                "subcategory_name": None,
                "payoree_id": None,
                "payoree_name": None,
                "needs_level": "Need",
                "baseline_amount": Decimal("120.00"),
                "suggested_amount": Decimal("130.00"),
                "id": 1,
            }
        ]

        draft = self.wizard.generate_budget_draft(
            target_months=3, method="median", starting_year=2025, starting_month=10
        )

        # Check draft structure
        self.assertIn("budget_items", draft)
        self.assertIn("periods", draft)
        self.assertIn("summary", draft)
        self.assertIn("method_used", draft)

        # Check periods generation
        self.assertEqual(len(draft["periods"]), 3)
        self.assertEqual(draft["periods"][0]["year"], 2025)
        self.assertEqual(draft["periods"][0]["month"], 10)

        # Check summary calculations
        summary = draft["summary"]
        self.assertEqual(summary["total_baseline"], Decimal("120.00"))
        self.assertEqual(summary["total_suggested"], Decimal("130.00"))
        self.assertEqual(summary["total_variance"], Decimal("10.00"))

    def test_generate_budget_draft_default_dates(self):
        """Test generating budget draft with default start dates."""
        self.mock_calculator.get_category_suggestions.return_value = []

        with patch("budgets.services.budget_wizard.date") as mock_date:
            mock_date.today.return_value = date(2025, 9, 15)

            draft = self.wizard.generate_budget_draft(target_months=3)

            # Should start with next month (October)
            self.assertEqual(draft["periods"][0]["year"], 2025)
            self.assertEqual(draft["periods"][0]["month"], 10)

    @patch("budgets.services.budget_wizard.transaction")
    def test_commit_budget_draft(self, mock_transaction):
        """Test committing budget draft to database."""
        # Create a mock transaction context
        mock_transaction.atomic.return_value.__enter__ = MagicMock()
        mock_transaction.atomic.return_value.__exit__ = MagicMock()

        draft_data = {
            "budget_items": [
                {
                    "category_id": self.category.id,
                    "category_name": "Groceries",
                    "subcategory_id": None,
                    "payoree_id": None,
                    "needs_level": "Need",
                    "suggested_amount": 130.00,
                    "id": 1,
                }
            ],
            "periods": [
                {"year": 2025, "month": 10},
                {"year": 2025, "month": 11},
                {"year": 2025, "month": 12},
            ],
        }

        with patch.object(
            self.wizard, "_create_budget_from_item"
        ) as mock_create_budget:
            mock_budget = MagicMock()
            mock_create_budget.return_value = mock_budget

            with patch.object(
                self.wizard, "_create_budget_periods"
            ) as mock_create_periods:
                result = self.wizard.commit_budget_draft(draft_data)

                # Should create budget and periods
                mock_create_budget.assert_called_once()
                mock_create_periods.assert_called_once()

                self.assertIn("created_budgets", result)
                self.assertEqual(len(result["created_budgets"]), 1)


class BudgetServiceIntegrationTest(TestCase):
    """Integration tests for budget services."""

    def setUp(self):
        """Set up test data."""
        self.category = Category.objects.create(name="Groceries", type="expense")
        self.account = FinancialAccount.objects.create(
            name="Test Checking Account",
            column_map={},
            description="Test checking account",
        )

        # Create some historical transactions
        Transaction.objects.create(
            transaction_date=date(2025, 8, 15),
            amount=Decimal("125.50"),
            description="Grocery shopping",
            bank_account=self.account,
            category=self.category,
            needs_level="Need",
            debit_credit="Debit",
        )

        Transaction.objects.create(
            transaction_date=date(2025, 7, 15),
            amount=Decimal("132.25"),
            description="Weekly groceries",
            bank_account=self.account,
            category=self.category,
            needs_level="Need",
            debit_credit="Debit",
        )

    def test_end_to_end_budget_creation(self):
        """Test complete budget creation flow."""
        wizard = BudgetWizard()

        # Generate draft
        draft = wizard.generate_budget_draft(
            target_months=3, method="median", starting_year=2025, starting_month=10
        )

        # Should have suggestions based on historical data
        self.assertGreater(len(draft["budget_items"]), 0)

        # Commit budget
        result = wizard.commit_budget_draft(draft)

        # Should create actual budget records
        self.assertIn("created_budgets", result)
        self.assertGreater(len(result["created_budgets"]), 0)

        # Check budget was actually created in database
        budget_id = result["created_budgets"][0]
        budget = Budget.objects.get(id=budget_id)

        self.assertEqual(budget.category, self.category)
        self.assertGreater(budget.amount, Decimal("0"))
        self.assertEqual(budget.start_date, date(2025, 10, 1))
        self.assertEqual(budget.end_date, date(2025, 12, 31))

        # Check budget periods were created
        periods = BudgetPeriod.objects.filter(budget=budget)
        self.assertEqual(periods.count(), 3)  # Oct, Nov, Dec
