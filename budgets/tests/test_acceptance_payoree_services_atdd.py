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
        self.assertIn(self.whole_foods.id, suggestions)
        self.assertIn(self.electric_company.id, suggestions)
        
        # Verify amounts are aggregated by payoree
        whole_foods_suggestion = suggestions[self.whole_foods.id]
        electric_suggestion = suggestions[self.electric_company.id]
        
        # Should suggest based on historical spending pattern
        self.assertEqual(whole_foods_suggestion['median'], Decimal('120.00'))
        self.assertEqual(electric_suggestion['median'], Decimal('85.00'))
        
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
        payoree_data = calculator._aggregate_by_payoree()
        
        # Then: The system shows spending patterns based on payoree-specific history
        self.assertIn(self.whole_foods.id, payoree_data)
        
        whole_foods_data = payoree_data[self.whole_foods.id]
        
        # Should have correct transaction count
        self.assertEqual(len(whole_foods_data['amounts']), 6)  # 6 months of data
        
        # Should have correct amounts (all $120.00)
        expected_amounts = [Decimal('120.00')] * 6
        self.assertEqual(whole_foods_data['amounts'], expected_amounts)
        
        # Should have payoree information
        self.assertEqual(whole_foods_data['payoree_name'], "Whole Foods")
        self.assertEqual(whole_foods_data['effective_category'], self.groceries_category.name)

    def test_budget_wizard_payoree_workflow(self):
        """
        ATDD ID: payoree_suggestion_workflow
        
        Given I start the budget wizard
        When it analyzes my transaction history
        Then it suggests allocations organized by payoree with recommended amounts
        """
        # Given: I start the budget wizard
        wizard = BudgetWizard()
        
        # When: It analyzes my transaction history
        suggestions = wizard.analyze_spending_patterns()
        
        # Then: It suggests allocations organized by payoree with recommended amounts
        self.assertIn('payoree_suggestions', suggestions)
        payoree_suggestions = suggestions['payoree_suggestions']
        
        # Should have suggestions for our test payorees
        whole_foods_found = False
        electric_found = False
        
        for suggestion in payoree_suggestions:
            if suggestion['payoree_id'] == self.whole_foods.id:
                whole_foods_found = True
                self.assertEqual(suggestion['payoree_name'], "Whole Foods")
                self.assertEqual(suggestion['suggested_amount'], Decimal('120.00'))
                self.assertEqual(suggestion['effective_category'], self.groceries_category.name)
            elif suggestion['payoree_id'] == self.electric_company.id:
                electric_found = True
                self.assertEqual(suggestion['payoree_name'], "Electric Company")
                self.assertEqual(suggestion['suggested_amount'], Decimal('85.00'))
                self.assertEqual(suggestion['effective_category'], self.utilities_category.name)
        
        self.assertTrue(whole_foods_found, "Whole Foods suggestion should be found")
        self.assertTrue(electric_found, "Electric Company suggestion should be found")

    def test_budget_wizard_payoree_allocation_creation(self):
        """
        ATDD ID: wizard_payoree_completion
        
        Given I complete the wizard
        When it creates allocations
        Then all allocations are payoree-based with properly derived category information
        """
        # Given: I complete the wizard with payoree-based suggestions
        wizard = BudgetWizard()
        suggestions = wizard.analyze_spending_patterns()
        
        # Simulate user accepting suggestions
        allocation_data = []
        for suggestion in suggestions['payoree_suggestions']:
            allocation_data.append({
                'payoree_id': suggestion['payoree_id'],
                'amount': suggestion['suggested_amount'],
                'is_ai_suggested': True,
                'baseline_amount': suggestion['suggested_amount']
            })
        
        # When: It creates allocations
        created_allocations = wizard.commit_budget_draft(
            budget_plan=self.budget_plan,
            allocations=allocation_data
        )
        
        # Then: All allocations are payoree-based with properly derived category information
        self.assertEqual(len(created_allocations), len(allocation_data))
        
        for allocation in created_allocations:
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
        for payoree_id, suggestion in suggestions.items():
            payoree = Payoree.objects.get(id=payoree_id)
            
            # Category should be inferred from payoree
            if payoree == self.whole_foods:
                self.assertEqual(suggestion['effective_category'], self.groceries_category.name)
            elif payoree == self.electric_company:
                self.assertEqual(suggestion['effective_category'], self.utilities_category.name)
            
            # Should include payoree information for adjustment
            self.assertEqual(suggestion['payoree_name'], payoree.name)
            self.assertIsNotNone(suggestion['median'])

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