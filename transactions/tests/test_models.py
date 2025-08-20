import pytest
import datetime as dt
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from transactions.models import Transaction, Category, Payoree, Tag


pytestmark = pytest.mark.django_db


class TestTransactionModel:
    """Comprehensive tests for the Transaction model."""

    def test_transaction_creation_with_minimal_fields(self):
        """Test creating a transaction with only required fields."""
        transaction = Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001", 
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Test Transaction",
            amount=Decimal("25.50"),
            account_type="checking"
        )
        
        assert transaction.source == "test.csv"
        assert transaction.bank_account == "CHK-1001"
        assert transaction.date == dt.date(2025, 1, 15)
        assert transaction.amount == Decimal("25.50")
        assert transaction.payoree is None
        assert transaction.category is None
        assert transaction.subcategory is None

    def test_transaction_creation_with_all_fields(self):
        """Test creating a transaction with all fields populated."""
        # Create related objects
        category = Category.objects.create(name="Food", type="expense")
        subcategory = Category.objects.create(name="Restaurants", type="expense", parent=category)
        payoree = Payoree.objects.create(name="Pizza Palace")
        tag = Tag.objects.create(name="business-meal")
        
        transaction = Transaction.objects.create(
            source="bank_export.csv",
            bank_account="CHK-1001",
            sheet_account="expense", 
            date=dt.date(2025, 1, 15),
            description="Pizza Palace lunch meeting",
            amount=Decimal("42.75"),
            account_type="checking",
            check_num="1234",
            memo="Client lunch - tax deductible",
            category=category,
            subcategory=subcategory,
            payoree=payoree
        )
        transaction.tags.add(tag)
        
        assert transaction.category == category
        assert transaction.subcategory == subcategory
        assert transaction.payoree == payoree
        assert transaction.check_num == "1234"
        assert transaction.memo == "Client lunch - tax deductible"
        assert tag in transaction.tags.all()

    def test_transaction_str_representation(self):
        """Test the string representation of a transaction."""
        transaction = Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Short description",
            amount=Decimal("25.50"),
            account_type="checking"
        )
        
        assert str(transaction) == "2025-01-15 - Short description"

    def test_transaction_str_truncation(self):
        """Test that long descriptions are truncated in string representation."""
        long_description = "This is a very long transaction description that should be truncated"
        transaction = Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001", 
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description=long_description,
            amount=Decimal("25.50"),
            account_type="checking"
        )
        
        str_repr = str(transaction)
        assert len(str_repr) <= 67  # Date (10) + " - " (3) + 50 chars + "..." (3) = 66
        assert str_repr.endswith("...")

    def test_unique_transaction_constraint(self):
        """Test that duplicate transactions are prevented by unique constraint."""
        # Create first transaction
        Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense", 
            date=dt.date(2025, 1, 15),
            description="Duplicate test",
            amount=Decimal("25.50"),
            account_type="checking"
        )
        
        # Attempt to create duplicate should raise IntegrityError
        with pytest.raises(IntegrityError):
            Transaction.objects.create(
                source="different.csv",  # Different source, but same key fields
                bank_account="CHK-1001",
                sheet_account="expense",
                date=dt.date(2025, 1, 15),
                description="Duplicate test", 
                amount=Decimal("25.50"),
                account_type="checking"
            )

    def test_transaction_with_different_amounts_allowed(self):
        """Test that transactions with different amounts are allowed."""
        Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Same description",
            amount=Decimal("25.50"),
            account_type="checking"
        )
        
        # Different amount should be allowed
        transaction2 = Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Same description",
            amount=Decimal("30.00"),  # Different amount
            account_type="checking"
        )
        
        assert transaction2.amount == Decimal("30.00")


class TestTransactionCategorization:
    """Tests for transaction categorization functionality."""

    def test_clean_method_validates_subcategory_parent(self):
        """Test that clean() validates subcategory belongs to category."""
        # Create categories
        food_category = Category.objects.create(name="Food", type="expense")
        transport_category = Category.objects.create(name="Transport", type="expense")
        restaurant_subcat = Category.objects.create(name="Restaurants", parent=food_category)
        
        transaction = Transaction(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Test transaction",
            amount=Decimal("25.50"),
            account_type="checking",
            category=transport_category,  # Wrong parent category
            subcategory=restaurant_subcat  # Belongs to food_category
        )
        
        with pytest.raises(ValidationError) as exc_info:
            transaction.clean()
        
        assert 'subcategory' in exc_info.value.error_dict
        assert 'must belong to category' in str(exc_info.value)

    def test_clean_method_allows_valid_category_subcategory(self):
        """Test that clean() allows valid category/subcategory combinations."""
        food_category = Category.objects.create(name="Food", type="expense")
        restaurant_subcat = Category.objects.create(name="Restaurants", parent=food_category)
        
        transaction = Transaction(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Test transaction",
            amount=Decimal("25.50"),
            account_type="checking",
            category=food_category,
            subcategory=restaurant_subcat
        )
        
        # Should not raise any exception
        transaction.clean()

    def test_get_top_level_category_from_category(self):
        """Test getting top-level category when category is set."""
        # Create category hierarchy
        top_category = Category.objects.create(name="Expenses", type="expense")
        food_category = Category.objects.create(name="Food", parent=top_category)
        restaurant_subcat = Category.objects.create(name="Restaurants", parent=food_category)
        
        transaction = Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Test transaction",
            amount=Decimal("25.50"),
            account_type="checking",
            category=food_category,  # Mid-level category
            subcategory=restaurant_subcat
        )
        
        assert transaction.get_top_level_category() == top_category

    def test_get_top_level_category_from_subcategory_fallback(self):
        """Test getting top-level category from subcategory when category is None."""
        top_category = Category.objects.create(name="Expenses", type="expense")
        food_category = Category.objects.create(name="Food", parent=top_category)
        restaurant_subcat = Category.objects.create(name="Restaurants", parent=food_category)
        
        transaction = Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Test transaction",
            amount=Decimal("25.50"),
            account_type="checking",
            category=None,  # No category set
            subcategory=restaurant_subcat  # But subcategory is set
        )
        
        assert transaction.get_top_level_category() == top_category

    def test_get_top_level_category_returns_none_when_no_categories(self):
        """Test that get_top_level_category returns None when no categories are set."""
        transaction = Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Test transaction",
            amount=Decimal("25.50"),
            account_type="checking"
        )
        
        assert transaction.get_top_level_category() is None


class TestTransactionErrors:
    """Tests for transaction error handling and display methods."""

    def test_has_categorization_error_false_when_no_error(self):
        """Test has_categorization_error returns False when no error is set."""
        transaction = Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Test transaction",
            amount=Decimal("25.50"),
            account_type="checking"
        )
        
        assert not transaction.has_categorization_error()

    def test_has_categorization_error_true_when_error_set(self):
        """Test has_categorization_error returns True when error is set."""
        transaction = Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Test transaction",
            amount=Decimal("25.50"),
            account_type="checking",
            categorization_error="AI_NO_SUBCATEGORY_SUGGESTION"
        )
        
        assert transaction.has_categorization_error()

    def test_get_error_description_returns_none_when_no_error(self):
        """Test get_error_description returns None when no error is set."""
        transaction = Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Test transaction",
            amount=Decimal("25.50"),
            account_type="checking"
        )
        
        assert transaction.get_error_description() is None

    def test_get_error_description_returns_human_readable_message(self):
        """Test get_error_description returns human-readable message for known errors."""
        transaction = Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Test transaction",
            amount=Decimal("25.50"),
            account_type="checking",
            categorization_error="AI_NO_SUBCATEGORY_SUGGESTION"
        )
        
        error_desc = transaction.get_error_description()
        assert error_desc == "AI could not suggest a subcategory"

    def test_get_error_description_returns_raw_error_for_unknown_codes(self):
        """Test get_error_description returns raw error for unknown error codes."""
        transaction = Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Test transaction",
            amount=Decimal("25.50"),
            account_type="checking",
            categorization_error="UNKNOWN_ERROR_CODE"
        )
        
        error_desc = transaction.get_error_description()
        assert error_desc == "UNKNOWN_ERROR_CODE"

    def test_is_successfully_categorized_true_when_payoree_and_no_error(self):
        """Test is_successfully_categorized returns True when payoree is set and no error."""
        payoree = Payoree.objects.create(name="Test Payoree")
        transaction = Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Test transaction",
            amount=Decimal("25.50"),
            account_type="checking",
            payoree=payoree
        )
        
        assert transaction.is_successfully_categorized()

    def test_is_successfully_categorized_false_when_no_payoree(self):
        """Test is_successfully_categorized returns False when no payoree is set."""
        transaction = Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Test transaction",
            amount=Decimal("25.50"),
            account_type="checking"
        )
        
        assert not transaction.is_successfully_categorized()

    def test_is_successfully_categorized_false_when_error_exists(self):
        """Test is_successfully_categorized returns False when categorization error exists."""
        payoree = Payoree.objects.create(name="Test Payoree")
        transaction = Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Test transaction",
            amount=Decimal("25.50"),
            account_type="checking",
            payoree=payoree,
            categorization_error="AI_NO_SUBCATEGORY_SUGGESTION"
        )
        
        assert not transaction.is_successfully_categorized()


class TestTransactionDisplayMethods:
    """Tests for transaction display methods."""

    def test_effective_category_display_with_category(self):
        """Test effective_category_display when category is set."""
        category = Category.objects.create(name="Food", type="expense")
        transaction = Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Test transaction",
            amount=Decimal("25.50"),
            account_type="checking",
            category=category
        )
        
        assert transaction.effective_category_display() == "Food"

    def test_effective_category_display_with_error(self):
        """Test effective_category_display when categorization error exists."""
        transaction = Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Test transaction",
            amount=Decimal("25.50"),
            account_type="checking",
            categorization_error="AI_NO_SUBCATEGORY_SUGGESTION"
        )
        
        assert transaction.effective_category_display() == "ERROR: AI_NO_SUBCATEGORY_SUGGESTION"

    def test_effective_category_display_uncategorized(self):
        """Test effective_category_display when no category or error."""
        transaction = Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Test transaction",
            amount=Decimal("25.50"),
            account_type="checking"
        )
        
        assert transaction.effective_category_display() == "Uncategorized"

    def test_effective_subcategory_display_with_subcategory(self):
        """Test effective_subcategory_display when subcategory is set."""
        category = Category.objects.create(name="Food", type="expense")
        subcategory = Category.objects.create(name="Restaurants", parent=category)
        transaction = Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Test transaction",
            amount=Decimal("25.50"),
            account_type="checking",
            subcategory=subcategory
        )
        
        assert transaction.effective_subcategory_display() == "Restaurants"

    def test_effective_payoree_display_with_payoree(self):
        """Test effective_payoree_display when payoree is set."""
        payoree = Payoree.objects.create(name="Pizza Palace")
        transaction = Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Test transaction",
            amount=Decimal("25.50"),
            account_type="checking",
            payoree=payoree
        )
        
        assert transaction.effective_payoree_display() == "Pizza Palace"

    def test_effective_payoree_display_unknown_when_no_payoree_no_error(self):
        """Test effective_payoree_display returns 'Unknown' when no payoree or error."""
        transaction = Transaction.objects.create(
            source="test.csv",
            bank_account="CHK-1001",
            sheet_account="expense",
            date=dt.date(2025, 1, 15),
            description="Test transaction",
            amount=Decimal("25.50"),
            account_type="checking"
        )
        
        assert transaction.effective_payoree_display() == "Unknown"
