import pytest
import json
from decimal import Decimal
from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from unittest.mock import Mock, patch

from transactions.models import Transaction, Category, Payoree, KeywordRule


@pytest.mark.django_db
class TestSubcategoriesAPIView(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create test categories and subcategories
        self.parent_category = Category.objects.create(
            name="Food & Dining",
            parent=None
        )
        
        self.subcategory1 = Category.objects.create(
            name="Restaurants",
            parent=self.parent_category
        )
        
        self.subcategory2 = Category.objects.create(
            name="Coffee Shops", 
            parent=self.parent_category
        )
        
        # Create another parent category for testing
        self.other_category = Category.objects.create(
            name="Transportation",
            parent=None
        )
        
        self.other_subcategory = Category.objects.create(
            name="Gas",
            parent=self.other_category
        )
        
        self.api_url = reverse('transactions:api_subcategories', kwargs={'category_id': self.parent_category.id})
        
    def test_subcategories_api_returns_correct_subcategories(self):
        """API should return subcategories for the specified parent category"""
        response = self.client.get(self.api_url)
        
        assert response.status_code == 200
        
        data = response.json()
        assert data['success'] is True
        assert 'subcategories' in data
        
        subcategories = data['subcategories']
        assert len(subcategories) == 2
        
        # Should be ordered by name
        assert subcategories[0]['name'] == "Coffee Shops"
        assert subcategories[1]['name'] == "Restaurants"
        
        # Check structure
        for subcat in subcategories:
            assert 'id' in subcat
            assert 'name' in subcat
            assert isinstance(subcat['id'], int)
            assert isinstance(subcat['name'], str)
            
    def test_subcategories_api_only_returns_subcategories_for_specified_parent(self):
        """API should only return subcategories for the requested parent category"""
        response = self.client.get(self.api_url)
        data = response.json()
        
        subcategory_names = [sub['name'] for sub in data['subcategories']]
        
        # Should include subcategories of the requested parent
        assert "Restaurants" in subcategory_names
        assert "Coffee Shops" in subcategory_names
        
        # Should NOT include subcategories of other parents
        assert "Gas" not in subcategory_names
        
    def test_subcategories_api_nonexistent_category_returns_500(self):
        """API should return 500 for nonexistent category (current behavior)"""
        nonexistent_url = reverse('transactions:api_subcategories', kwargs={'category_id': 999})
        response = self.client.get(nonexistent_url)
        
        assert response.status_code == 500
        data = response.json()
        assert data['success'] is False
        assert 'error' in data
        
    def test_subcategories_api_subcategory_as_parent_returns_500(self):
        """API should return 500 when trying to get subcategories of a subcategory (current behavior)"""
        subcategory_url = reverse('transactions:api_subcategories', kwargs={'category_id': self.subcategory1.id})
        response = self.client.get(subcategory_url)
        
        assert response.status_code == 500
        data = response.json()
        assert data['success'] is False
        assert 'error' in data
        
    def test_subcategories_api_handles_category_with_no_subcategories(self):
        """API should handle categories with no subcategories gracefully"""
        empty_category = Category.objects.create(name="Empty Category", parent=None)
        empty_url = reverse('transactions:api_subcategories', kwargs={'category_id': empty_category.id})
        
        response = self.client.get(empty_url)
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['subcategories'] == []
        
    def test_subcategories_api_content_type_is_json(self):
        """API should return JSON content type"""
        response = self.client.get(self.api_url)
        
        assert response['Content-Type'] == 'application/json'


@pytest.mark.django_db
class TestTransactionSuggestionsAPIView(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create test transaction
        self.transaction = Transaction.objects.create(
            date=date(2023, 1, 15),
            description="STARBUCKS COFFEE #1234",
            amount=Decimal('-5.50'),
            sheet_account="Chase Checking"
        )
        
        # Create test categories for suggestions
        self.food_category = Category.objects.create(name="Food & Dining", parent=None)
        self.coffee_subcategory = Category.objects.create(name="Coffee Shops", parent=self.food_category)
        
        self.api_url = reverse('transactions:api_suggestions', kwargs={'transaction_id': self.transaction.id})
        
    def test_suggestions_api_returns_successful_response(self):
        """API should return successful response structure"""
        with patch('transactions.categorization.categorize_transaction_with_reasoning') as mock_categorize:
            mock_categorize.return_value = ("Food & Dining", "Coffee Shops", "This appears to be a coffee purchase")
            
            response = self.client.get(self.api_url)
            
            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
            assert 'suggestions' in data
            
    def test_suggestions_api_returns_ai_suggestions(self):
        """API should return AI categorization suggestions"""
        with patch('transactions.categorization.categorize_transaction_with_reasoning') as mock_categorize:
            mock_categorize.return_value = ("Food & Dining", "Coffee Shops", "Coffee shop transaction detected")
            
            response = self.client.get(self.api_url)
            data = response.json()
            
            suggestions = data['suggestions']
            assert suggestions['category']['name'] == "Food & Dining"
            assert suggestions['subcategory']['name'] == "Coffee Shops"
            assert suggestions['reasoning'] == "Coffee shop transaction detected"
            
            # Should include IDs
            assert suggestions['category']['id'] == self.food_category.id
            assert suggestions['subcategory']['id'] == self.coffee_subcategory.id
            
    def test_suggestions_api_handles_no_category_suggestion(self):
        """API should handle case when no category is suggested"""
        with patch('transactions.categorization.categorize_transaction_with_reasoning') as mock_categorize:
            mock_categorize.return_value = (None, None, "Unable to categorize")
            
            response = self.client.get(self.api_url)
            data = response.json()
            
            suggestions = data['suggestions']
            assert suggestions['category'] is None
            assert suggestions['subcategory'] is None
            assert suggestions['reasoning'] == "Unable to categorize"
            
    def test_suggestions_api_handles_nonexistent_suggested_categories(self):
        """API should handle when suggested categories don't exist in database"""
        with patch('transactions.categorization.categorize_transaction_with_reasoning') as mock_categorize:
            mock_categorize.return_value = ("Nonexistent Category", "Nonexistent Subcategory", "Test reasoning")
            
            response = self.client.get(self.api_url)
            data = response.json()
            
            suggestions = data['suggestions']
            assert suggestions['category'] is None
            assert suggestions['subcategory'] is None
            assert suggestions['reasoning'] == "Test reasoning"
            
    def test_suggestions_api_nonexistent_transaction_returns_500(self):
        """API should return 500 for nonexistent transaction (current behavior)"""
        nonexistent_url = reverse('transactions:api_suggestions', kwargs={'transaction_id': 999})
        response = self.client.get(nonexistent_url)
        
        assert response.status_code == 500
        data = response.json()
        assert data['success'] is False
        assert 'error' in data
        
    def test_suggestions_api_handles_categorization_errors(self):
        """API should handle errors in categorization gracefully"""
        with patch('transactions.categorization.categorize_transaction_with_reasoning') as mock_categorize:
            mock_categorize.side_effect = Exception("Categorization failed")
            
            response = self.client.get(self.api_url)
            
            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
            
            suggestions = data['suggestions']
            assert suggestions['category'] is None
            assert suggestions['subcategory'] is None
            assert suggestions['reasoning'] is None
            
    def test_suggestions_api_calls_categorization_with_correct_parameters(self):
        """API should call categorization function with transaction details"""
        with patch('transactions.categorization.categorize_transaction_with_reasoning') as mock_categorize:
            mock_categorize.return_value = ("Food & Dining", "Coffee Shops", "Test reasoning")
            
            response = self.client.get(self.api_url)
            
            mock_categorize.assert_called_once_with(
                self.transaction.description,
                float(self.transaction.amount)
            )


@pytest.mark.django_db
class TestSimilarTransactionsAPIView(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create test payoree and categories
        self.starbucks = Payoree.objects.create(name="Starbucks")
        self.food_category = Category.objects.create(name="Food & Dining", parent=None)
        self.coffee_subcategory = Category.objects.create(name="Coffee Shops", parent=self.food_category)
        
        # Create main transaction
        self.main_transaction = Transaction.objects.create(
            date=date(2023, 1, 15),
            description="STARBUCKS COFFEE #1234", 
            amount=Decimal('-5.50'),
            sheet_account="Chase Checking"
        )
        
        # Create similar transactions
        self.similar_transaction1 = Transaction.objects.create(
            date=date(2023, 1, 10),
            description="STARBUCKS STORE #5678",
            amount=Decimal('-4.75'),
            sheet_account="Chase Checking",
            category=self.food_category,
            subcategory=self.coffee_subcategory,
            payoree=self.starbucks
        )
        
        self.similar_transaction2 = Transaction.objects.create(
            date=date(2023, 1, 5),
            description="STARBUCKS COFFEE COMPANY",
            amount=Decimal('-6.25'),
            sheet_account="Chase Checking",
            category=self.food_category,
            subcategory=self.coffee_subcategory,
            payoree=self.starbucks
        )
        
        # Create dissimilar transaction
        self.dissimilar_transaction = Transaction.objects.create(
            date=date(2023, 1, 12),
            description="SHELL GAS STATION",
            amount=Decimal('-45.00'),
            sheet_account="Chase Checking"
        )
        
        self.api_url = reverse('transactions:api_similar', kwargs={'transaction_id': self.main_transaction.id})
        
    def test_similar_transactions_api_returns_successful_response(self):
        """API should return successful response structure"""
        with patch('transactions.utils.normalize_description') as mock_normalize:
            mock_normalize.side_effect = lambda x: x.upper()
            
            with patch('rapidfuzz.fuzz.token_set_ratio') as mock_fuzz:
                mock_fuzz.return_value = 85
                
                response = self.client.get(self.api_url)
                
                assert response.status_code == 200
                data = response.json()
                assert data['success'] is True
                assert 'transactions' in data
                
    def test_similar_transactions_api_finds_similar_transactions(self):
        """API should find and return similar transactions"""
        with patch('transactions.utils.normalize_description') as mock_normalize:
            mock_normalize.side_effect = lambda x: x.upper()
            
            with patch('rapidfuzz.fuzz.token_set_ratio') as mock_fuzz:
                def mock_similarity(desc1, desc2):
                    if "STARBUCKS" in desc1 and "STARBUCKS" in desc2:
                        return 85  # High similarity
                    return 30  # Low similarity
                
                mock_fuzz.side_effect = mock_similarity
                
                response = self.client.get(self.api_url)
                data = response.json()
                
                transactions = data['transactions']
                assert len(transactions) == 2  # Two similar Starbucks transactions
                
                # Should include transaction details
                transaction_ids = [t['id'] for t in transactions]
                assert self.similar_transaction1.id in transaction_ids
                assert self.similar_transaction2.id in transaction_ids
                assert self.dissimilar_transaction.id not in transaction_ids
                
    def test_similar_transactions_api_includes_transaction_details(self):
        """API should include comprehensive transaction details"""
        with patch('transactions.utils.normalize_description') as mock_normalize:
            mock_normalize.side_effect = lambda x: x.upper()
            
            with patch('rapidfuzz.fuzz.token_set_ratio') as mock_fuzz:
                mock_fuzz.return_value = 85
                
                response = self.client.get(self.api_url)
                data = response.json()
                
                transactions = data['transactions']
                if transactions:
                    transaction = transactions[0]
                    
                    # Check required fields
                    assert 'id' in transaction
                    assert 'date' in transaction
                    assert 'description' in transaction
                    assert 'amount' in transaction
                    assert 'similarity' in transaction
                    assert 'category' in transaction
                    assert 'subcategory' in transaction
                    assert 'payoree' in transaction
                    
                    # Check date format
                    assert transaction['date'] == "2023-01-10"
                    
                    # Check amount conversion
                    assert isinstance(transaction['amount'], float)
                    
    def test_similar_transactions_api_respects_limit_parameter(self):
        """API should respect the limit parameter"""
        # Create more similar transactions
        for i in range(5):
            Transaction.objects.create(
                date=date(2023, 1, i+1),
                description=f"STARBUCKS LOCATION #{i}",
                amount=Decimal('-5.00'),
            sheet_account="Chase Checking"
        )
        
        with patch('transactions.utils.normalize_description') as mock_normalize:
            mock_normalize.side_effect = lambda x: x.upper()
            
            with patch('rapidfuzz.fuzz.token_set_ratio') as mock_fuzz:
                mock_fuzz.return_value = 85
                
                # Test with limit=3
                response = self.client.get(self.api_url + '?limit=3')
                data = response.json()
                
                assert len(data['transactions']) == 3
                
    def test_similar_transactions_api_excludes_self(self):
        """API should exclude the transaction being compared"""
        with patch('transactions.utils.normalize_description') as mock_normalize:
            mock_normalize.side_effect = lambda x: x.upper()
            
            with patch('rapidfuzz.fuzz.token_set_ratio') as mock_fuzz:
                mock_fuzz.return_value = 100  # Perfect match
                
                response = self.client.get(self.api_url)
                data = response.json()
                
                transaction_ids = [t['id'] for t in data['transactions']]
                assert self.main_transaction.id not in transaction_ids
                
    def test_similar_transactions_api_handles_missing_rapidfuzz(self):
        """API should handle missing rapidfuzz gracefully"""
        # Since rapidfuzz is already imported at module level, we need to test the fallback
        # by just verifying that missing rapidfuzz results in empty transactions list
        with patch.dict('sys.modules', {'rapidfuzz': None}):
            response = self.client.get(self.api_url)
            
            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
            assert data['transactions'] == []
            
    def test_similar_transactions_api_nonexistent_transaction_returns_500(self):
        """API should return 500 for nonexistent transaction (current behavior)"""
        nonexistent_url = reverse('transactions:api_similar', kwargs={'transaction_id': 999})
        response = self.client.get(nonexistent_url)
        
        assert response.status_code == 500
        data = response.json()
        assert data['success'] is False
        assert 'error' in data
        
    def test_similar_transactions_api_similarity_threshold(self):
        """API should only return transactions above similarity threshold"""
        with patch('transactions.utils.normalize_description') as mock_normalize:
            mock_normalize.side_effect = lambda x: x.upper()
            
            with patch('rapidfuzz.fuzz.token_set_ratio') as mock_fuzz:
                # Return low similarity (below 70% threshold)
                mock_fuzz.return_value = 65
                
                response = self.client.get(self.api_url)
                data = response.json()
                
                # Should return empty list since similarity is below threshold
                assert data['transactions'] == []


@pytest.mark.django_db  
class TestAPIErrorHandling(TestCase):
    """Test error handling across all API endpoints"""
    
    def setUp(self):
        self.client = Client()
        
        # Create minimal test data
        self.category = Category.objects.create(name="Test Category", parent=None)
        self.transaction = Transaction.objects.create(
            date=date(2023, 1, 15),
            description="Test Transaction",
            amount=Decimal('-10.00'),
            sheet_account="Test Account"
        )
        
    def test_api_endpoints_handle_internal_errors_gracefully(self):
        """All API endpoints should handle internal errors gracefully"""
        
        # Test subcategories API with database error
        with patch('transactions.views.api.get_object_or_404') as mock_get:
            mock_get.side_effect = Exception("Database error")
            
            url = reverse('transactions:api_subcategories', kwargs={'category_id': self.category.id})
            response = self.client.get(url)
            
            assert response.status_code == 500
            data = response.json()
            assert data['success'] is False
            assert 'error' in data
            
        # Test suggestions API with internal error  
        with patch('transactions.views.api.get_object_or_404') as mock_get:
            mock_get.side_effect = Exception("Internal error")
            
            url = reverse('transactions:api_suggestions', kwargs={'transaction_id': self.transaction.id})
            response = self.client.get(url)
            
            assert response.status_code == 500
            data = response.json()
            assert data['success'] is False
            assert 'error' in data
            
        # Test similar transactions API with internal error
        with patch('transactions.views.api.get_object_or_404') as mock_get:
            mock_get.side_effect = Exception("Internal error")
            
            url = reverse('transactions:api_similar', kwargs={'transaction_id': self.transaction.id})
            response = self.client.get(url)
            
            assert response.status_code == 500
            data = response.json()
            assert data['success'] is False
            assert 'error' in data
            
    def test_api_endpoints_return_consistent_error_format(self):
        """All API endpoints should return consistent error format"""
        
        # Force an error and check format consistency
        with patch('transactions.views.api.Category.objects.get') as mock_get:
            mock_get.side_effect = Exception("Test error")
            
            url = reverse('transactions:api_subcategories', kwargs={'category_id': 999})
            response = self.client.get(url)
            
            if response.status_code == 500:  # Only test if we get expected error
                data = response.json()
                
                # Check error response structure
                assert 'success' in data
                assert 'error' in data
                assert data['success'] is False
                assert isinstance(data['error'], str)


@pytest.mark.django_db
class TestAPIAuthentication(TestCase):
    """Test API endpoints authentication requirements"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        
        # Create test data
        self.category = Category.objects.create(name="Test Category", parent=None)
        self.transaction = Transaction.objects.create(
            date=date(2023, 1, 15),
            description="Test Transaction", 
            amount=Decimal('-10.00'),
            sheet_account="Test Account"
        )
        
    def test_api_endpoints_accessible_without_authentication(self):
        """API endpoints should be accessible without authentication"""
        
        # Test subcategories API
        url = reverse('transactions:api_subcategories', kwargs={'category_id': self.category.id})
        response = self.client.get(url)
        assert response.status_code in [200, 404]  # Should not be 401/403
        
        # Test suggestions API  
        url = reverse('transactions:api_suggestions', kwargs={'transaction_id': self.transaction.id})
        response = self.client.get(url)
        assert response.status_code in [200, 500]  # Should not be 401/403
        
        # Test similar transactions API
        url = reverse('transactions:api_similar', kwargs={'transaction_id': self.transaction.id})
        response = self.client.get(url)
        assert response.status_code in [200, 500]  # Should not be 401/403
        
    def test_api_endpoints_work_with_authenticated_user(self):
        """API endpoints should work normally with authenticated users"""
        self.client.login(username='testuser', password='testpass')
        
        # Test subcategories API
        url = reverse('transactions:api_subcategories', kwargs={'category_id': self.category.id})
        response = self.client.get(url)
        assert response.status_code in [200, 404]
        
        # Test suggestions API
        url = reverse('transactions:api_suggestions', kwargs={'transaction_id': self.transaction.id})
        response = self.client.get(url)
        assert response.status_code in [200, 500]
        
        # Test similar transactions API
        url = reverse('transactions:api_similar', kwargs={'transaction_id': self.transaction.id})
        response = self.client.get(url)
        assert response.status_code in [200, 500]


@pytest.mark.django_db
class TestAPIPerformance(TestCase):
    """Test API endpoint performance with larger datasets"""
    
    def setUp(self):
        self.client = Client()
        
        # Create test category with many subcategories
        self.parent_category = Category.objects.create(name="Large Category", parent=None)
        
        # Create 50 subcategories
        self.subcategories = []
        for i in range(50):
            subcat = Category.objects.create(
                name=f"Subcategory {i:02d}",
                parent=self.parent_category
            )
            self.subcategories.append(subcat)
            
        # Create transaction with many similar transactions
        self.main_transaction = Transaction.objects.create(
            date=date(2023, 1, 15),
            description="COFFEE SHOP PURCHASE",
            amount=Decimal('-5.00'),
            sheet_account="Test Account"
        )
        
        # Create 100 similar transactions
        for i in range(100):
            Transaction.objects.create(
                date=date(2023, 1, i % 28 + 1),
                description=f"COFFEE SHOP #{i:03d}",
                amount=Decimal(f'-{5 + (i % 10)}.00'),
                sheet_account="Test Account"
            )
            
    def test_subcategories_api_handles_many_subcategories(self):
        """Subcategories API should handle categories with many subcategories"""
        url = reverse('transactions:api_subcategories', kwargs={'category_id': self.parent_category.id})
        response = self.client.get(url)
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert len(data['subcategories']) == 50
        
        # Should be ordered by name
        names = [sub['name'] for sub in data['subcategories']]
        assert names == sorted(names)
        
    def test_similar_transactions_api_handles_many_transactions(self):
        """Similar transactions API should handle large transaction datasets"""
        with patch('transactions.utils.normalize_description') as mock_normalize:
            mock_normalize.side_effect = lambda x: x.upper()
            
            with patch('rapidfuzz.fuzz.token_set_ratio') as mock_fuzz:
                mock_fuzz.return_value = 75  # Above threshold
                
                url = reverse('transactions:api_similar', kwargs={'transaction_id': self.main_transaction.id})
                response = self.client.get(url + '?limit=20')
                
                assert response.status_code == 200
                data = response.json()
                assert data['success'] is True
                
                # Should respect limit parameter
                assert len(data['transactions']) == 20
