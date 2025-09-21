"""
Tests for budget views and API endpoints.

Covers all budget-related views including wizard, list, detail, and API endpoints.
"""
import json
from decimal import Decimal
from datetime import date
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client
from django.urls import reverse

from budgets.models import Budget, BudgetPeriod
from transactions.models import Category, Payoree


class BudgetViewsTest(TestCase):
    """Test budget views."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.category = Category.objects.create(
            name="Groceries",
            type="expense"
        )
        self.payoree = Payoree.objects.create(
            name="Whole Foods"
        )
        
        # Create test budget
        self.budget = Budget.objects.create(
            category=self.category,
            amount=Decimal('600.00'),
            start_date=date(2025, 10, 1),
            end_date=date(2025, 12, 31),
            needs_level='Need'
        )
        
        # Create budget period
        self.budget_period = BudgetPeriod.objects.create(
            budget=self.budget,
            period_year=2025,
            period_month=10,
            actual_spent=Decimal('150.00')
        )
        
    def test_budget_list_view(self):
        """Test budget list view."""
        url = reverse('budgets:list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Budgets')
        self.assertContains(response, 'Groceries')
        self.assertContains(response, '$600.00')
        
    def test_budget_list_view_empty(self):
        """Test budget list view with no budgets."""
        Budget.objects.all().delete()
        
        url = reverse('budgets:list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No Budgets Yet')
        self.assertContains(response, 'Create Your First Budget')
        
    def test_budget_detail_view(self):
        """Test budget detail view."""
        url = reverse('budgets:detail', kwargs={'pk': self.budget.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Groceries')
        self.assertContains(response, '$600.00')
        self.assertContains(response, '$150.00')  # Spent amount
        
    def test_budget_detail_view_not_found(self):
        """Test budget detail view with non-existent budget."""
        url = reverse('budgets:detail', kwargs={'pk': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 404)
        
    def test_budget_wizard_view_get(self):
        """Test budget wizard view GET request."""
        url = reverse('budgets:wizard')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Budget Wizard')
        self.assertContains(response, 'Configuration')
        self.assertContains(response, 'target-months')
        
    def test_budget_wizard_context(self):
        """Test budget wizard view context data."""
        url = reverse('budgets:wizard')
        response = self.client.get(url)
        
        # Check template context
        self.assertIn('page_title', response.context)
        self.assertEqual(response.context['page_title'], 'Budget Wizard')


class BudgetAPIViewsTest(TestCase):
    """Test budget API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.category = Category.objects.create(
            name="Groceries", 
            type="expense"
        )
        
    @patch('budgets.views.BudgetWizard')
    def test_api_generate_draft(self, mock_wizard_class):
        """Test API endpoint for generating budget draft."""
        # Mock wizard instance and response
        mock_wizard = MagicMock()
        mock_wizard_class.return_value = mock_wizard
        mock_wizard.generate_budget_draft.return_value = {
            'budget_items': [
                {
                    'category_id': self.category.id,
                    'category_name': 'Groceries',
                    'baseline_amount': Decimal('120.00'),
                    'suggested_amount': Decimal('130.00'),
                    'id': 1
                }
            ],
            'periods': [
                {'year': 2025, 'month': 10, 'display': 'October 2025'}
            ],
            'summary': {
                'total_baseline': Decimal('120.00'),
                'total_suggested': Decimal('130.00'),
                'total_variance': Decimal('10.00'),
                'item_count': 1
            },
            'method_used': 'median'
        }
        
        url = reverse('budgets:api_generate_draft')
        response = self.client.post(url, {
            'target_months': 3,
            'method': 'median',
            'starting_year': 2025,
            'starting_month': 10
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Parse JSON response
        data = json.loads(response.content)
        self.assertIn('budget_items', data)
        self.assertIn('periods', data)
        self.assertIn('summary', data)
        
        # Check wizard was called with correct parameters
        mock_wizard.generate_budget_draft.assert_called_once_with(
            target_months=3,
            method='median',
            starting_year=2025,
            starting_month=10
        )
        
    def test_api_generate_draft_invalid_method(self):
        """Test API endpoint with invalid data."""
        url = reverse('budgets:api_generate_draft')
        response = self.client.post(url, {
            'target_months': 'invalid',  # Invalid data
            'method': 'median'
        })
        
        self.assertEqual(response.status_code, 400)
        
    def test_api_generate_draft_missing_csrf(self):
        """Test API endpoint without CSRF token."""
        # Create client without CSRF
        client = Client(enforce_csrf_checks=True)
        
        url = reverse('budgets:api_generate_draft')
        response = client.post(url, {
            'target_months': 3,
            'method': 'median'
        })
        
        self.assertEqual(response.status_code, 403)
        
    @patch('budgets.views.BudgetWizard')
    def test_api_commit_budget(self, mock_wizard_class):
        """Test API endpoint for committing budget."""
        # Mock wizard instance and response
        mock_wizard = MagicMock()
        mock_wizard_class.return_value = mock_wizard
        mock_wizard.commit_budget_draft.return_value = {
            'created_budgets': [1, 2],
            'created_periods': 6,
            'success': True
        }
        
        draft_data = {
            'budget_items': [
                {
                    'category_id': self.category.id,
                    'suggested_amount': 130.00,
                    'needs_level': 'Need'
                }
            ],
            'periods': [
                {'year': 2025, 'month': 10},
                {'year': 2025, 'month': 11},
                {'year': 2025, 'month': 12}
            ]
        }
        
        url = reverse('budgets:api_commit_budget')
        response = self.client.post(
            url,
            json.dumps(draft_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Parse JSON response
        data = json.loads(response.content)
        self.assertIn('created_budgets', data)
        self.assertEqual(len(data['created_budgets']), 2)
        
        # Check wizard was called
        mock_wizard.commit_budget_draft.assert_called_once()
        
    def test_api_commit_budget_invalid_json(self):
        """Test API endpoint with invalid JSON."""
        url = reverse('budgets:api_commit_budget')
        response = self.client.post(
            url,
            'invalid json',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
    @patch('budgets.views.BaselineCalculator')
    def test_api_baseline_spending(self, mock_calculator_class):
        """Test API endpoint for baseline spending calculation."""
        # Mock calculator instance and response  
        mock_calculator = MagicMock()
        mock_calculator_class.return_value = mock_calculator
        mock_calculator.get_baseline_spending.return_value = Decimal('125.50')
        
        url = reverse('budgets:api_baseline')
        response = self.client.post(url, {
            'category_id': self.category.id,
            'months_back': 6,
            'method': 'median'
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Parse JSON response
        data = json.loads(response.content)
        self.assertIn('baseline_amount', data)
        self.assertEqual(data['baseline_amount'], '125.50')
        
        # Check calculator was called with correct parameters
        mock_calculator.get_baseline_spending.assert_called_once_with(
            category=self.category,
            subcategory=None,
            payoree=None,
            needs_level=None,
            months_back=6,
            method='median'
        )
        
    def test_api_baseline_spending_no_category(self):
        """Test baseline API without category specified."""
        url = reverse('budgets:api_baseline')
        response = self.client.post(url, {
            'months_back': 6,
            'method': 'median'
        })
        
        self.assertEqual(response.status_code, 400)


class BudgetViewIntegrationTest(TestCase):
    """Integration tests for budget views."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.category = Category.objects.create(
            name="Groceries",
            type="expense"
        )
        
    def test_full_budget_creation_flow(self):
        """Test complete budget creation workflow."""
        # Step 1: Load wizard page
        wizard_url = reverse('budgets:wizard')
        response = self.client.get(wizard_url)
        self.assertEqual(response.status_code, 200)
        
        # Step 2: Generate draft (would normally be AJAX)
        # For testing, we'll create a budget directly
        budget = Budget.objects.create(
            category=self.category,
            amount=Decimal('400.00'),
            start_date=date(2025, 10, 1),
            end_date=date(2025, 12, 31),
            needs_level='Need'
        )
        
        # Step 3: View budget in list
        list_url = reverse('budgets:list')
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Groceries')
        self.assertContains(response, '$400.00')
        
        # Step 4: View budget details
        detail_url = reverse('budgets:detail', kwargs={'pk': budget.pk})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Groceries')
        self.assertContains(response, '$400.00')
        
    def test_budget_list_pagination(self):
        """Test budget list pagination."""
        # Create multiple budgets
        for i in range(15):
            category = Category.objects.create(
                name=f"Category {i}",
                type="expense"
            )
            Budget.objects.create(
                category=category,
                amount=Decimal(f'{100 + i}.00'),
                start_date=date(2025, 10, 1),
                end_date=date(2025, 12, 31),
                needs_level='Need'
            )
            
        # Test first page
        list_url = reverse('budgets:list')
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)
        
        # Should have pagination if more than 10 budgets
        if Budget.objects.count() > 10:
            self.assertContains(response, 'pagination')


class BudgetViewPermissionsTest(TestCase):
    """Test budget view permissions and security."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.category = Category.objects.create(
            name="Groceries",
            type="expense"
        )
        
        self.budget = Budget.objects.create(
            category=self.category,
            amount=Decimal('400.00'),
            start_date=date(2025, 10, 1),
            end_date=date(2025, 12, 31),
            needs_level='Need'
        )
        
    def test_budget_views_no_auth_required(self):
        """Test that budget views don't require authentication (single-user app)."""
        # List view
        list_url = reverse('budgets:list')
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)
        
        # Detail view
        detail_url = reverse('budgets:detail', kwargs={'pk': self.budget.pk})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        
        # Wizard view
        wizard_url = reverse('budgets:wizard')
        response = self.client.get(wizard_url)
        self.assertEqual(response.status_code, 200)
        
    def test_api_csrf_protection(self):
        """Test that API endpoints are CSRF protected."""
        # Create client with CSRF enforcement
        client = Client(enforce_csrf_checks=True)
        
        # Test generate draft API
        url = reverse('budgets:api_generate_draft')
        response = client.post(url, {
            'target_months': 3,
            'method': 'median'
        })
        self.assertEqual(response.status_code, 403)
        
        # Test commit budget API
        url = reverse('budgets:api_commit_budget')
        response = client.post(
            url,
            '{"budget_items": []}',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 403)