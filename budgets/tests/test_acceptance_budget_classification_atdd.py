"""
ATDD Tests for Budget by Classification Analysis Feature

These tests follow the acceptance criteria defined in:
docs/user_stories/budgets/budget_by_classification_atdd.md
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import datetime, date

from budgets.models import BudgetPlan, BudgetAllocation
from transactions.models import Category, Payoree, Transaction

# Import ATDD infrastructure
try:
    from atdd_tracker import atdd_test
except ImportError:
    # Fallback decorator if atdd_tracker not available
    def atdd_test(story, criteria_id, description):
        def decorator(func):
            func.atdd_story = story
            func.atdd_criteria_id = criteria_id
            func.atdd_description = description
            return func
        return decorator


class TestBudgetClassificationATDD(TestCase):
    """ATDD tests for Budget by Classification Analysis feature."""

    def setUp(self):
        """Set up test data."""
        User = get_user_model()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        
        # Create test categories
        self.groceries_category = Category.objects.create(
            name="Groceries",
            type="expense"
        )
        self.food_subcategory = Category.objects.create(
            name="Food",
            type="expense",
            parent=self.groceries_category
        )
        self.utilities_category = Category.objects.create(
            name="Utilities",
            type="expense"
        )
        
        # Create test payoree
        self.test_payoree = Payoree.objects.create(
            name="Test Store",
            default_category=self.groceries_category
        )
        
        # Create test budget plan
        self.budget_plan = BudgetPlan.objects.create(
            name="Normal",
            year=2025,
            month=10,
            is_active=True
        )
        
        # Create test budget allocations
        self.grocery_allocation = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan,
            category=self.groceries_category,
            amount=Decimal('500.00')
        )

    @atdd_test(
        story="budget_by_classification", 
        criteria_id="classification_type_selection",
        description="User can select classification type from dropdown"
    )
    def test_classification_type_selection(self):
        """Given I want to analyze budget by classification, when I access the page, then I can select classification type."""
        
        # When: User accesses the budget classification page
        url = reverse('budgets:classification_analysis')
        response = self.client.get(url)
        
        # Then: Page loads successfully
        self.assertEqual(response.status_code, 200)
        
        # And: Classification type dropdown is present
        self.assertContains(response, 'id="classification-type"')
        self.assertContains(response, 'Category')
        self.assertContains(response, 'Subcategory') 
        self.assertContains(response, 'Payoree')

    @atdd_test(
        story="budget_by_classification",
        criteria_id="hierarchical_category_selection", 
        description="When Subcategory is selected, user must first select category"
    )
    def test_hierarchical_category_selection(self):
        """Given subcategory classification type, when I select it, then category dropdown appears first."""
        
        # When: User selects classification type "subcategory"
        url = reverse('budgets:classification_analysis')
        response = self.client.get(url, {'classification_type': 'subcategory'})
        
        # Then: Page loads successfully
        self.assertEqual(response.status_code, 200)
        
        # And: Category dropdown is present and required
        self.assertContains(response, 'id="category-select"')
        self.assertContains(response, self.groceries_category.name)
        
        # And: Subcategory dropdown is present but initially disabled/empty
        self.assertContains(response, 'id="subcategory-select"')

    @atdd_test(
        story="budget_by_classification",
        criteria_id="single_classification_focus",
        description="Page displays data for ONE selected classification at a time"
    )
    def test_single_classification_focus(self):
        """Given I select a specific classification, when page loads, then only data for that classification is shown."""
        
        # When: User selects a specific category
        url = reverse('budgets:classification_analysis')
        response = self.client.get(url, {
            'classification_type': 'category',
            'category_id': self.groceries_category.id
        })
        
        # Then: Page loads successfully
        self.assertEqual(response.status_code, 200)
        
        # And: Selected classification is displayed in context
        self.assertContains(response, self.groceries_category.name)
        
        # And: Only one classification's data is shown (not multiple)
        self.assertContains(response, 'selected-classification')

    @atdd_test(
        story="budget_by_classification", 
        criteria_id="historical_vs_budget_columns",
        description="Side-by-side display of 12 months historical and budget data"
    )
    def test_historical_vs_budget_columns(self):
        """Given selected classification, when viewing data, then I see historical and budget columns side by side."""
        
        # Given: Some historical transactions exist
        Transaction.objects.create(
            date=date(2024, 9, 15),
            amount=Decimal('-120.50'),
            description="Grocery shopping",
            category=self.groceries_category,
            payoree=self.test_payoree
        )
        
        # When: User views classification analysis
        url = reverse('budgets:classification_analysis')
        response = self.client.get(url, {
            'classification_type': 'category',
            'category_id': self.groceries_category.id
        })
        
        # Then: Page displays both historical and budget columns
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'historical-column')
        self.assertContains(response, 'budget-column')
        
        # And: Monthly data is shown (12 months)
        self.assertContains(response, 'monthly-data')

    @atdd_test(
        story="budget_by_classification",
        criteria_id="inline_budget_editing",
        description="User can click budget values to edit them directly"
    )
    def test_inline_budget_editing(self):
        """Given budget values are displayed, when I click them, then I can edit inline with auto-save."""
        
        # When: User views classification with budget data
        url = reverse('budgets:classification_analysis')
        response = self.client.get(url, {
            'classification_type': 'category', 
            'category_id': self.groceries_category.id
        })
        
        # Then: Editable budget fields are present
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'editable-budget')
        self.assertContains(response, 'data-allocation-id')
        
        # And: JavaScript for inline editing is included
        self.assertContains(response, 'inline-edit')

    @atdd_test(
        story="budget_by_classification",
        criteria_id="real_data_display",
        description="Historical and budget values display real data from database"
    )
    def test_real_data_display(self):
        """Given transactions and budget allocations exist, when viewing classification analysis, then real values are displayed."""
        
        # Given: Historical transactions exist
        Transaction.objects.create(
            date=date(2024, 9, 15),
            amount=Decimal('-150.75'),
            description="Grocery Store A",
            category=self.groceries_category,
            payoree=self.test_payoree
        )
        Transaction.objects.create(
            date=date(2024, 9, 22),
            amount=Decimal('-89.50'),
            description="Grocery Store B", 
            category=self.groceries_category,
            payoree=self.test_payoree
        )
        
        # When: User views category analysis
        url = reverse('budgets:classification_analysis')
        response = self.client.get(url, {
            'classification_type': 'category',
            'category_id': self.groceries_category.id
        })
        
        # Then: Real transaction data is displayed 
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Groceries')  # Category name
        
        # And: Budget allocation value is shown
        self.assertContains(response, '$500.00')  # Budget allocation amount
        
        # And: Page structure indicates data is present
        self.assertContains(response, 'historical-column')
        self.assertContains(response, 'budget-column')
        self.assertContains(response, 'monthly-data')

    @atdd_test(
        story="budget_by_classification",
        criteria_id="ajax_budget_update",
        description="AJAX endpoint updates budget allocations and returns success"
    )
    def test_ajax_budget_update(self):
        """Given budget allocation exists, when I update via AJAX, then amount is saved and response indicates success."""
        
        # Given: Budget allocation exists
        allocation = self.grocery_allocation
        original_amount = allocation.amount
        new_amount = Decimal('600.00')
        
        # When: AJAX update is sent
        update_url = reverse('budgets:classification_update')
        response = self.client.post(update_url, {
            'allocation_id': allocation.id,
            'amount': str(new_amount)
        })
        
        # Then: Response indicates success
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data['success'])
        self.assertEqual(response_data['new_amount'], '600.00')
        
        # And: Database is updated
        allocation.refresh_from_db()
        self.assertEqual(allocation.amount, new_amount)
        self.assertNotEqual(allocation.amount, original_amount)