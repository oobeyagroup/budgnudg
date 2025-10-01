"""
ATDD Tests for Payoree-Centric Budget Allocation

These tests implement the acceptance criteria from:
docs/user_stories/budgets/payoree_centric_budget_management_atdd.md

User Story: Payoree-Only Budget Allocation Creation
As a budget planner, I want to create budget allocations by specifying only 
the payoree and amount so that budgeting becomes more concrete and actionable 
around who I actually pay.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from decimal import Decimal
from datetime import date

from budgets.models import BudgetPlan, BudgetAllocation
from transactions.models import Category, Payoree


class TestPayoreeCentricAllocationATDD(TestCase):
    """ATDD tests for payoree-centric budget allocation creation."""

    def setUp(self):
        """Set up test data for payoree allocation testing."""
        # Create test categories
        self.groceries_category = Category.objects.create(
            name="Groceries", type="expense"
        )
        self.utilities_category = Category.objects.create(
            name="Utilities", type="expense"
        )
        self.food_subcategory = Category.objects.create(
            name="Food", type="expense", parent=self.groceries_category
        )
        
        # Create test payorees with default categories
        self.whole_foods = Payoree.objects.create(
            name="Whole Foods", 
            default_category=self.groceries_category,
            default_subcategory=self.food_subcategory
        )
        self.electric_company = Payoree.objects.create(
            name="Electric Company",
            default_category=self.utilities_category
        )
        self.misc_payoree = Payoree.objects.create(
            name="Miscellaneous",
            default_category=self.groceries_category
        )
        
        # Create test budget plan
        self.current_budget_plan = BudgetPlan.objects.create(
            name="October Budget",
            year=2025,
            month=10,
            is_active=True
        )

    def test_payoree_allocation_creation(self):
        """
        ATDD ID: payoree_allocation_creation
        
        Given I want to create a budget allocation
        When I select a payoree and enter an amount
        Then the system creates an allocation with categories automatically 
        derived from the payoree's defaults
        """
        # Given: I want to create a budget allocation
        # When: I select a payoree and enter an amount
        allocation = BudgetAllocation.objects.create(
            budget_plan=self.current_budget_plan,
            payoree=self.whole_foods,
            amount=Decimal("500.00")
        )
        
        # Then: The system creates an allocation with categories automatically derived
        self.assertEqual(allocation.payoree, self.whole_foods)
        self.assertEqual(allocation.amount, Decimal("500.00"))
        self.assertEqual(allocation.budget_plan, self.current_budget_plan)
        
        # Verify the allocation was saved to database
        saved_allocation = BudgetAllocation.objects.get(id=allocation.id)
        self.assertEqual(saved_allocation.payoree, self.whole_foods)
        self.assertEqual(saved_allocation.amount, Decimal("500.00"))

    def test_effective_category_display(self):
        """
        ATDD ID: effective_category_display
        
        Given a payoree-based allocation exists
        When I view the allocation
        Then I see the effective category and subcategory derived from the payoree
        """
        # Given: A payoree-based allocation exists
        allocation = BudgetAllocation.objects.create(
            budget_plan=self.current_budget_plan,
            payoree=self.whole_foods,
            amount=Decimal("500.00")
        )
        
        # When: I view the allocation
        # Then: I see the effective category and subcategory derived from the payoree
        self.assertEqual(allocation.effective_category, self.groceries_category)
        self.assertEqual(allocation.effective_subcategory, self.food_subcategory)
        
        # Test payoree without subcategory
        utilities_allocation = BudgetAllocation.objects.create(
            budget_plan=self.current_budget_plan,
            payoree=self.electric_company,
            amount=Decimal("200.00")
        )
        
        self.assertEqual(utilities_allocation.effective_category, self.utilities_category)
        self.assertIsNone(utilities_allocation.effective_subcategory)

    def test_payoree_validation(self):
        """
        ATDD ID: payoree_validation
        
        Given I attempt to create an allocation
        When I don't specify a payoree
        Then the system prevents creation with a clear validation error
        """
        # Given: I attempt to create an allocation
        # When: I don't specify a payoree
        allocation = BudgetAllocation(
            budget_plan=self.current_budget_plan,
            # payoree=None,  # Missing required payoree
            amount=Decimal("500.00")
        )
        
        # Then: The system prevents creation with a clear validation error
        with self.assertRaises(ValidationError) as context:
            allocation.full_clean()
        
        error_messages = str(context.exception)
        self.assertIn("Payoree is required", error_messages)

    def test_duplicate_allocation_prevention(self):
        """
        ATDD ID: duplicate_allocation_prevention
        
        Given an allocation already exists for a payoree in a budget plan
        When I try to create another allocation for the same payoree
        Then the system prevents duplicate creation
        """
        # Given: An allocation already exists for a payoree in a budget plan
        BudgetAllocation.objects.create(
            budget_plan=self.current_budget_plan,
            payoree=self.whole_foods,
            amount=Decimal("500.00")
        )
        
        # When: I try to create another allocation for the same payoree
        # Then: The system prevents duplicate creation
        with self.assertRaises(IntegrityError):
            BudgetAllocation.objects.create(
                budget_plan=self.current_budget_plan,
                payoree=self.whole_foods,  # Same payoree
                amount=Decimal("300.00")   # Different amount
            )

    def test_multiple_payorees_same_category(self):
        """
        Additional test: Multiple payorees can have allocations in the same category
        """
        # Create another grocery store
        safeway = Payoree.objects.create(
            name="Safeway",
            default_category=self.groceries_category
        )
        
        # Both payorees can have allocations in the same budget plan
        whole_foods_allocation = BudgetAllocation.objects.create(
            budget_plan=self.current_budget_plan,
            payoree=self.whole_foods,
            amount=Decimal("300.00")
        )
        
        safeway_allocation = BudgetAllocation.objects.create(
            budget_plan=self.current_budget_plan,
            payoree=safeway,
            amount=Decimal("200.00")
        )
        
        # Both should have the same effective category
        self.assertEqual(whole_foods_allocation.effective_category, self.groceries_category)
        self.assertEqual(safeway_allocation.effective_category, self.groceries_category)
        
        # But they should be separate allocations
        self.assertNotEqual(whole_foods_allocation.id, safeway_allocation.id)

    def test_allocation_properties_and_methods(self):
        """
        Test allocation property methods work correctly with payoree-centric model
        """
        allocation = BudgetAllocation.objects.create(
            budget_plan=self.current_budget_plan,
            payoree=self.whole_foods,
            amount=Decimal("500.00"),
            baseline_amount=Decimal("450.00")
        )
        
        # Test basic properties
        self.assertEqual(allocation.year, 2025)
        self.assertEqual(allocation.month, 10)
        self.assertEqual(allocation.period_display, "October 2025")
        
        # Test variance calculations
        self.assertEqual(allocation.get_variance_vs_baseline(), Decimal("50.00"))
        expected_variance_percentage = ((Decimal("500.00") - Decimal("450.00")) / Decimal("450.00")) * 100
        self.assertAlmostEqual(allocation.get_variance_percentage(), expected_variance_percentage, places=2)
        
        # Test date properties
        self.assertEqual(allocation.start_date, date(2025, 10, 1))
        self.assertEqual(allocation.end_date, date(2025, 10, 31))
        
        # Test active status
        self.assertTrue(allocation.is_active)  # Budget plan is active

    def test_misc_payoree_allocation(self):
        """
        Test creating allocations for miscellaneous expenses
        """
        misc_allocation = BudgetAllocation.objects.create(
            budget_plan=self.current_budget_plan,
            payoree=self.misc_payoree,
            amount=Decimal("100.00")
        )
        
        self.assertEqual(misc_allocation.payoree.name, "Miscellaneous")
        self.assertEqual(misc_allocation.effective_category, self.groceries_category)
        self.assertEqual(misc_allocation.amount, Decimal("100.00"))