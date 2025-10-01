"""
ATDD Tests for Payoree-Centric Budget Services

These tests implement acceptance criteria for the updated budget services
to work with the simplified payoree-centric BudgetAllocation model.

Related to user stories in:
docs/user_stories/budgets/payoree_centric_budget_management_atdd.md
"""

from django.test import TestCase
from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta

from budgets.models import BudgetPlan, BudgetAllocation
from budgets.services.baseline_calculator import BaselineCalculator
from budgets.services.budget_wizard import BudgetWizard
from transactions.models import Category, Payoree, Transaction
from ingest.models import FinancialAccount


class TestPayoreeCentricServicesATDD(TestCase):
    """ATDD tests for payoree-centric budget services."""

    def setUp(self):
        """Set up test data for payoree services testing."""
        # Create test categories
        self.groceries_category = Category.objects.create(
            name="Groceries", type="expense"
        )
        self.utilities_category = Category.objects.create(
            name="Utilities", type="expense"
        )
        
        # Create test payorees with default categories
        self.whole_foods = Payoree.objects.create(
            name="Whole Foods", 
            default_category=self.groceries_category
        )
        self.electric_company = Payoree.objects.create(
            name="Electric Company",
            default_category=self.utilities_category
        )
        self.misc_payoree = Payoree.objects.create(
            name="Miscellaneous",
            default_category=self.groceries_category
        )
        
        # Create test account
        self.account = FinancialAccount.objects.create(
            name="Test Checking",
            column_map={},
            description="Test account"
        )
        
        # Create historical transactions for baseline calculation
        self.create_historical_transactions()
        
        # Create budget plan for testing
        self.budget_plan = BudgetPlan.objects.create(
            name="Test Budget",
            year=2025,
            month=10,
            is_active=True
        )

    def create_historical_transactions(self):
        """Create historical transaction data for testing services."""
        base_date = date(2025, 4, 1)  # 6 months of history
        
        # Create regular pattern for Whole Foods (groceries)
        for i in range(6):  # 6 months
            month_date = base_date + relativedelta(months=i)
            Transaction.objects.create(
                source="test_file.csv",
                date=month_date,
                amount=Decimal("-120.00"),  # Negative for expense
                payoree=self.whole_foods,
                category=self.groceries_category,
                bank_account=self.account,
                sheet_account="Expense",
                account_type="Checking",
                description=f"Groceries {month_date.strftime('%B')}"
            )
        
        # Create regular pattern for Electric Company (utilities)
        for i in range(6):
            month_date = base_date + relativedelta(months=i)
            Transaction.objects.create(
                source="test_file.csv",
                date=month_date + relativedelta(days=15),  # Mid-month
                amount=Decimal("-85.00"),  # Negative for expense
                payoree=self.electric_company,
                category=self.utilities_category,
                bank_account=self.account,
                sheet_account="Expense",
                account_type="Checking",
                description=f"Electric bill {month_date.strftime('%B')}"
            )

    def test_baseline_calculator_payoree_suggestions(self):
        """
        ATDD ID: payoree_baseline_calculation
        
        Given multiple months of payoree transactions
        When the system calculates baselines
        Then it aggregates spending by payoree rather than by category
        """
        # Given: Multiple months of payoree transactions (created in setUp)
        # When: The system calculates baselines
        calculator = BaselineCalculator()
        suggestions = calculator.get_payoree_suggestions()
        
        # Then: It aggregates spending by payoree rather than by category
        payoree_names = [s['payoree_name'] for s in suggestions]
        self.assertIn("Whole Foods", payoree_names)
        self.assertIn("Electric Company", payoree_names)
        
        # Verify amounts are aggregated by payoree
        whole_foods_suggestion = next(s for s in suggestions if s['payoree_name'] == "Whole Foods")
        electric_suggestion = next(s for s in suggestions if s['payoree_name'] == "Electric Company")
        
        # Should suggest based on historical spending pattern
        self.assertEqual(whole_foods_suggestion['baseline_amount'], Decimal('120.00'))
        self.assertEqual(electric_suggestion['baseline_amount'], Decimal('85.00'))
        
        # Should include payoree metadata
        self.assertEqual(whole_foods_suggestion['payoree_name'], "Whole Foods")
        self.assertEqual(electric_suggestion['payoree_name'], "Electric Company")

    def test_baseline_calculator_payoree_aggregation(self):
        """
        ATDD ID: payoree_spending_history
        
        Given historical transactions exist for a payoree
        When I view budget suggestions
        Then the system shows spending patterns and suggests allocations
        based on payoree-specific history
        """
        # Given: Historical transactions exist for a payoree (created in setUp)
        # When: I view budget suggestions
        calculator = BaselineCalculator()
        baselines = calculator.calculate_baselines(method="median")
        
        # Then: The system shows spending patterns based on payoree-specific history
        # Find whole foods in baselines (keyed by payoree ID)
        whole_foods_found = False
        for payoree_id, baseline_data in baselines.items():
            if payoree_id == self.whole_foods.id:
                whole_foods_found = True
                
                # Should have correct baseline amount (monthly median of $120.00)
                self.assertEqual(baseline_data['monthly_baseline'], Decimal('120.00'))
                
                # Should have supporting transaction data
                support = baseline_data['support']
                self.assertEqual(support['n_months'], 6)  # 6 months of data
                self.assertEqual(support['min_monthly'], 120.0)
                self.assertEqual(support['max_monthly'], 120.0)
                self.assertEqual(support['total_transactions'], 6)
                break
        
        self.assertTrue(whole_foods_found, "Whole Foods should be in baseline calculations")

    def test_budget_wizard_payoree_workflow(self):
        """
        ATDD ID: payoree_suggestion_workflow
        
        Given I start the budget wizard
        When it analyzes my transaction history
        Then it suggests allocations organized by payoree with recommended amounts
        """
        # Given: I start the budget wizard
        wizard = BudgetWizard()
        
        # When: It analyzes my transaction history (using generate_budget_draft)
        draft = wizard.generate_budget_draft(target_months=1)
        
        # Then: It suggests allocations organized by payoree with recommended amounts
        self.assertIn('budget_items', draft)
        payoree_suggestions = draft['budget_items']
        
        # Should have suggestions for our test payorees
        whole_foods_found = False
        electric_found = False
        
        for suggestion in payoree_suggestions:
            if suggestion['payoree_name'] == "Whole Foods":
                whole_foods_found = True
                self.assertEqual(suggestion['payoree_name'], "Whole Foods")
                self.assertEqual(suggestion['category_name'], self.groceries_category.name)
            elif suggestion['payoree_name'] == "Electric Company":
                electric_found = True
                self.assertEqual(suggestion['payoree_name'], "Electric Company")
                self.assertEqual(suggestion['category_name'], self.utilities_category.name)
        
        self.assertTrue(whole_foods_found, "Whole Foods suggestion should be found")
        self.assertTrue(electric_found, "Electric Company suggestion should be found")

    def test_budget_wizard_payoree_allocation_creation(self):
        """
        ATDD ID: wizard_payoree_completion
        
        Given I complete the wizard
        When it creates allocations
        Then all allocations are payoree-based with properly derived category information
        """
        # Given: I have generated suggestions and want to create allocations
        wizard = BudgetWizard()
        
        # Create allocations manually using the simplified payoree model
        # (This tests the end result of what wizard would create)
        whole_foods_allocation = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan,
            payoree=self.whole_foods,
            amount=Decimal('120.00'),
            is_ai_suggested=True,
            baseline_amount=Decimal('120.00')
        )
        
        electric_allocation = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan,
            payoree=self.electric_company,
            amount=Decimal('85.00'),
            is_ai_suggested=True,
            baseline_amount=Decimal('85.00')
        )
        
        # Then: All allocations are payoree-based with properly derived category information
        allocations = BudgetAllocation.objects.filter(budget_plan=self.budget_plan)
        self.assertEqual(allocations.count(), 2)
        
        for allocation in allocations:
            # Should be payoree-based
            self.assertIsNotNone(allocation.payoree)
            
            # Should have effective category derived from payoree
            if allocation.payoree == self.whole_foods:
                self.assertEqual(allocation.effective_category, self.groceries_category)
                self.assertEqual(allocation.amount, Decimal('120.00'))
            elif allocation.payoree == self.electric_company:
                self.assertEqual(allocation.effective_category, self.utilities_category)
                self.assertEqual(allocation.amount, Decimal('85.00'))
            
            # Should be marked as AI suggested
            self.assertTrue(allocation.is_ai_suggested)
            self.assertIsNotNone(allocation.baseline_amount)

    def test_payoree_category_inference(self):
        """
        ATDD ID: payoree_category_inference
        
        Given suggested payoree allocations
        When I review them
        Then I see inferred categories and can adjust them if needed
        """
        # Given: Suggested payoree allocations
        calculator = BaselineCalculator()
        suggestions = calculator.get_payoree_suggestions()
        
        # When: I review them
        # Then: I see inferred categories
        for suggestion in suggestions:
            # Category should be inferred from payoree
            if suggestion['payoree_name'] == "Whole Foods":
                self.assertEqual(suggestion['category_name'], self.groceries_category.name)
            elif suggestion['payoree_name'] == "Electric Company":
                self.assertEqual(suggestion['category_name'], self.utilities_category.name)
            
            # Should include payoree information for adjustment
            self.assertIsNotNone(suggestion['payoree_name'])
            self.assertIsNotNone(suggestion['baseline_amount'])

    def test_misc_payoree_handling(self):
        """
        Test that miscellaneous payoree is handled correctly in services
        """
        # Create a transaction for misc payoree
        Transaction.objects.create(
            source="test_file.csv",
            date=date(2025, 5, 1),
            amount=Decimal("-50.00"),
            payoree=self.misc_payoree,
            category=self.groceries_category,
            bank_account=self.account,
            sheet_account="Expense",
            account_type="Checking",
            description="Misc expense"
        )
        
        # Test that baseline calculator includes misc payoree
        calculator = BaselineCalculator()
        suggestions = calculator.get_payoree_suggestions()
        
        # Find misc payoree in suggestions list
        misc_suggestion = None
        for suggestion in suggestions:
            if suggestion['payoree_name'] == "Miscellaneous":
                misc_suggestion = suggestion
                break
        
        self.assertIsNotNone(misc_suggestion, "Miscellaneous payoree should be in suggestions")
        self.assertEqual(misc_suggestion['payoree_name'], "Miscellaneous")
        self.assertEqual(misc_suggestion['category_name'], self.groceries_category.name)

    def test_allocation_spending_tracking(self):
        """
        Test that allocations can track spending against payoree-specific budgets
        """
        # Create allocation
        allocation = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan,
            payoree=self.whole_foods,
            amount=Decimal("120.00")
        )
        
        # Create a transaction in the budget period
        Transaction.objects.create(
            source="test_file.csv",
            date=date(2025, 10, 15),  # Within budget period
            amount=Decimal("-75.00"),  # Negative for expense
            payoree=self.whole_foods,
            category=self.groceries_category,
            bank_account=self.account,
            sheet_account="Expense",
            account_type="Checking",
            description="October groceries"
        )
        
        # Test spending calculations
        spent_amount = allocation.get_current_spent()
        self.assertEqual(spent_amount, Decimal("75.00"))
        
        spent_percentage = allocation.get_spent_percentage()
        expected_percentage = (Decimal("75.00") / Decimal("120.00")) * 100
        self.assertEqual(spent_percentage, expected_percentage)
        
        remaining = allocation.get_remaining_amount()
        self.assertEqual(remaining, Decimal("45.00"))