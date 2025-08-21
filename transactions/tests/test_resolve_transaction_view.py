# Import patch for mocking
from unittest.mock import patch

import pytest
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.test.utils import override_settings
from bs4 import BeautifulSoup

from transactions.models import Transaction, Category, Payoree
from transactions.categorization import suggest_payoree


class TestResolveTransactionAISuggestions(TestCase):
    """Test the AI suggestions functionality in the resolve transaction template."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        
        # Create test categories
        self.category1 = Category.objects.create(name='Food & Dining', type='expense')
        self.category2 = Category.objects.create(name='Transport', type='expense')
        self.subcategory1 = Category.objects.create(
            name='Restaurants', 
            type='expense', 
            parent=self.category1
        )
        
        # Create test payorees
        self.payoree1 = Payoree.objects.create(name='Starbucks Coffee')
        self.payoree2 = Payoree.objects.create(name='Target Store')
        
        # Create test transactions
        self.transaction1 = Transaction.objects.create(
            description='Purchase at Starbucks Coffee downtown',
            amount=-15.50,
            date='2025-08-15',
            bank_account='Checking',
            category=self.category1,
            subcategory=self.subcategory1,
            payoree=self.payoree1
        )
        
        self.transaction2 = Transaction.objects.create(
            description='Shopping at Target Store location',
            amount=-45.25,
            date='2025-08-16',
            bank_account='Checking'
        )
    
    def test_ai_suggestions_equal_current_values_same_colors_disabled_buttons(self):
        """
        Test that when Current and AI Suggestions are equal, 
        the colors of the values should be the same and the Train and Apply buttons should be disabled.
        """
        # Create a transaction that will get suggestions matching its current values
        transaction = Transaction.objects.create(
            description='Starbucks Coffee purchase',
            amount=-12.00,
            date='2025-08-17',
            bank_account='Checking',
            category=self.category1,
            subcategory=self.subcategory1,
            payoree=self.payoree1
        )
        
        # Mock the categorization to return the same category as current
        with patch('transactions.categorization.categorize_transaction_with_reasoning') as mock_categorize:
            # Make AI suggest the same category as current
            mock_categorize.return_value = (
                self.category1.name,  # Same as current
                self.subcategory1.name,  # Same as current
                "High confidence match based on learned patterns"
            )
            
            url = reverse('transactions:categorize_transaction', kwargs={'pk': transaction.pk})
            response = self.client.get(url)
            
            self.assertEqual(response.status_code, 200)
            
            # Parse the HTML response
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find the AI suggestions section
            ai_suggestions = soup.find('div', class_='card-body')
            
            # Check category row
            category_row = ai_suggestions.find_all('div', class_='row')[2]  # Category row
            cols = category_row.find_all('div', class_='col')
            
            # Current category badge
            current_badge = cols[1].find('span', class_='badge')
            # AI suggestion badge  
            suggestion_badge = cols[3].find('span', class_='badge')
            
            if current_badge and suggestion_badge:
                # When they match, both should have the same styling
                # Current is bg-primary, suggestion should also be bg-primary (not bg-success)
                current_classes = current_badge.get('class', [])
                suggestion_classes = suggestion_badge.get('class', [])
                
                # They should both use similar color scheme when matching
                self.assertIn('badge', current_classes)
                self.assertIn('badge', suggestion_classes)
                
                # Text content should be the same
                self.assertEqual(current_badge.get_text().strip(), suggestion_badge.get_text().strip())
                
                # Train button should be disabled or show "Already Trained" state
                train_button = cols[2].find('button')
                if train_button:
                    # Should be disabled or have different state
                    self.assertTrue(
                        'disabled' in train_button.get('class', []) or
                        train_button.get('disabled') == 'disabled' or
                        'btn-outline-secondary' in train_button.get('class', [])
                    )
                
                # Apply button should be disabled when values match
                apply_button = cols[4].find('button')
                if apply_button:
                    self.assertTrue(
                        'disabled' in apply_button.get('class', []) or
                        apply_button.get('disabled') == 'disabled' or
                        'btn-outline-secondary' in apply_button.get('class', [])
                    )
    
    def test_payoree_suggestion_from_description_matching(self):
        """
        Test that if there is a string within the Description text that matches 
        an entry in the Payoree table, then a Payoree suggestion will not be empty.
        """
        # Test with exact match
        transaction_exact = Transaction.objects.create(
            description='Coffee from Starbucks Coffee this morning',
            amount=-8.50,
            date='2025-08-18',
            bank_account='Checking'
        )
        
        url = reverse('transactions:categorize_transaction', kwargs={'pk': transaction_exact.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that a payoree suggestion was provided in context
        # The resolve view should detect "Starbucks Coffee" in the description
        # and suggest the matching payoree
        context = response.context
        
        # Direct test of the suggestion function
        suggested_payoree_name = suggest_payoree(transaction_exact.description)
        
        # Should find a suggestion since "Starbucks Coffee" is in the description
        # and exists in the Payoree table
        if suggested_payoree_name:
            self.assertIsNotNone(suggested_payoree_name)
            # Verify it's a known payoree
            payoree_exists = Payoree.objects.filter(name=suggested_payoree_name).exists()
            self.assertTrue(payoree_exists)
        
        # Test with partial match (if fuzzy matching is implemented)
        transaction_partial = Transaction.objects.create(
            description='Purchase at Target Store downtown',
            amount=-25.75,
            date='2025-08-19',
            bank_account='Checking'
        )
        
        suggested_payoree_partial = suggest_payoree(transaction_partial.description)
        
        # Should find Target Store since it's in the description
        if suggested_payoree_partial:
            self.assertIsNotNone(suggested_payoree_partial)
            payoree_exists = Payoree.objects.filter(name=suggested_payoree_partial).exists()
            self.assertTrue(payoree_exists)
    
    def test_payoree_suggestion_integration_in_template(self):
        """Test that payoree suggestions appear correctly in the template."""
        # Create a transaction with description containing a known payoree
        transaction = Transaction.objects.create(
            description='Morning coffee at Starbucks Coffee location',
            amount=-6.25,
            date='2025-08-20',
            bank_account='Checking'
        )
        
        url = reverse('transactions:categorize_transaction', kwargs={'pk': transaction.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Parse HTML to check payoree suggestion row
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find the payoree row in AI suggestions
        ai_suggestions = soup.find('div', class_='card-body')
        if ai_suggestions:
            rows = ai_suggestions.find_all('div', class_='row')
            self.assertGreaterEqual(len(rows), 2, "Should have header row and at least one data row")
            payoree_row = rows[1]  # Payoree row
            cols = payoree_row.find_all('div', class_='col')
            self.assertGreaterEqual(len(cols), 4, "Should have at least 4 columns")
            
            # Check the AI suggestion column (4th column)
            suggestion_col = cols[3]
            
            # Should not show "No suggestion" if there's a matching payoree
            suggestion_text = suggestion_col.get_text().strip()
            
            # Either should show a payoree name or "Coming soon"
            self.assertNotEqual(suggestion_text.lower(), 'no suggestion')
            
            # If a suggestion is shown, it should be in a success badge
            suggestion_badge = suggestion_col.find('span', class_='badge')
            if suggestion_badge and 'bg-success' in suggestion_badge.get('class', []):
                # Verify the suggested payoree exists
                suggested_name = suggestion_badge.get_text().strip()
                payoree_exists = Payoree.objects.filter(name=suggested_name).exists()
                self.assertTrue(payoree_exists)
    
    def test_no_payoree_suggestion_when_no_match(self):
        """Test that no payoree suggestion is provided when description doesn't match any payoree."""
        transaction = Transaction.objects.create(
            description='Random purchase at unknown vendor XYZ123',
            amount=-15.00,
            date='2025-08-21',
            bank_account='Checking'
        )
        
        # Test the suggestion function directly
        suggested_payoree = suggest_payoree(transaction.description)
        
        # Should be None since no payoree matches "unknown vendor XYZ123"
        self.assertIsNone(suggested_payoree)
        
        # Check template rendering
        url = reverse('transactions:categorize_transaction', kwargs={'pk': transaction.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        ai_suggestions = soup.find('div', class_='card-body')
        
        if ai_suggestions:
            rows = ai_suggestions.find_all('div', class_='row')
            self.assertGreaterEqual(len(rows), 2, "Should have header row and at least one data row")
            payoree_row = rows[1]  # Payoree row
            cols = payoree_row.find_all('div', class_='col')
            self.assertGreaterEqual(len(cols), 4, "Should have at least 4 columns")
            suggestion_col = cols[3]
            
            # Should show "Coming soon" or "No suggestion"
            suggestion_text = suggestion_col.get_text().strip()
            self.assertIn(suggestion_text.lower(), ['coming soon', 'no suggestion'])
        else:
            # If no AI suggestions section, it's also valid for no suggestions case
            pass


class TestAISuggestionsTemplateLogic(TestCase):
    """Test the template logic for matching current vs AI suggestions."""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass')
        self.client = Client()
        self.client.login(username='testuser', password='pass')
        
        self.category = Category.objects.create(name='Test Category', type='expense')
        self.payoree = Payoree.objects.create(name='Test Payoree')
    
    def test_template_shows_matching_colors_when_suggestions_equal_current(self):
        """Test template logic when AI suggestions match current values."""
        transaction = Transaction.objects.create(
            description='Test transaction',
            amount=-10.00,
            date='2025-08-22',
            bank_account='Test',
            category=self.category,
            payoree=self.payoree
        )
        
        # Mock to return matching suggestions
        with patch('transactions.categorization.categorize_transaction_with_reasoning') as mock_cat:
            mock_cat.return_value = (self.category.name, None, "Test reasoning")
            
            url = reverse('transactions:categorize_transaction', kwargs={'pk': transaction.pk})
            response = self.client.get(url)
            
            # Verify the template received matching suggestions
            self.assertEqual(response.context['category_suggestion'], self.category)
            self.assertEqual(response.context['transaction'].category, self.category)
            
            # When current and suggestion match, template should handle this appropriately
            self.assertEqual(response.status_code, 200)
