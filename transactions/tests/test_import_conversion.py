"""
Test for the import conversion service that provides clean ImportRow → Transaction conversion.
"""

import pytest
from decimal import Decimal
from datetime import date

from transactions.services.import_conversion import (
    ImportRowData,
    ImportRowConverter,
    converter,
)
from transactions.models import Transaction, Category, Payoree
from ingest.models import FinancialAccount

pytestmark = pytest.mark.django_db


class TestImportRowConverter:
    """Test the ImportRowConverter service."""

    def test_basic_conversion_success(self):
        """Test successful conversion of ImportRow data to Transaction."""
        # Create a test bank account
        bank_account = FinancialAccount.objects.create(
            name="test_bank",
            column_map={
                "Date": "date",
                "Amount": "amount",
                "Description": "description",
            },
        )

        # Create import data
        import_data = ImportRowData(
            row_index=1,
            date=date(2024, 1, 15),
            amount=Decimal("100.50"),
            description="Test transaction",
            bank_account=bank_account,
            source_filename="test.csv",
        )

        # Convert to transaction
        result = converter.convert_import_row_to_transaction(import_data)

        # Verify success
        assert result.success is True
        assert result.transaction is not None
        assert result.errors == []
        assert result.row_index == 1

        # Verify transaction fields
        txn = result.transaction
        assert txn.date == date(2024, 1, 15)
        assert txn.amount == Decimal("100.50")
        assert txn.description == "Test transaction"
        assert txn.bank_account == bank_account
        assert txn.source == "test.csv"

    def test_conversion_with_reversed_amounts(self):
        """Test conversion with reversed amounts."""
        bank_account = FinancialAccount.objects.create(
            name="test_bank",
            column_map={
                "Date": "date",
                "Amount": "amount",
                "Description": "description",
            },
        )

        import_data = ImportRowData(
            row_index=1,
            date=date(2024, 1, 15),
            amount=Decimal("100.50"),
            description="Test transaction",
            bank_account=bank_account,
        )

        # Convert with reversed amounts
        result = converter.convert_import_row_to_transaction(
            import_data, reverse_amounts=True
        )

        assert result.success is True
        assert result.transaction.amount == Decimal("-100.50")

    def test_conversion_with_category_suggestions(self):
        """Test conversion with AI category suggestions."""
        bank_account = FinancialAccount.objects.create(
            name="test_bank",
            column_map={
                "Date": "date",
                "Amount": "amount",
                "Description": "description",
            },
        )

        # Create test categories
        parent_category = Category.objects.create(name="Food & Dining", type="expense")
        subcategory = Category.objects.create(
            name="Restaurants", type="expense", parent=parent_category
        )

        import_data = ImportRowData(
            row_index=1,
            date=date(2024, 1, 15),
            amount=Decimal("25.00"),
            description="Restaurant meal",
            suggestions={"subcategory": "Restaurants"},
            bank_account=bank_account,
        )

        result = converter.convert_import_row_to_transaction(import_data)

        assert result.success is True
        txn = result.transaction
        assert txn.category == parent_category
        assert txn.subcategory == subcategory

    def test_conversion_with_payoree_suggestions(self):
        """Test conversion with AI payoree suggestions."""
        bank_account = FinancialAccount.objects.create(
            name="test_bank",
            column_map={
                "Date": "date",
                "Amount": "amount",
                "Description": "description",
            },
        )

        import_data = ImportRowData(
            row_index=1,
            date=date(2024, 1, 15),
            amount=Decimal("50.00"),
            description="Gas station purchase",
            suggestions={"payoree": "Shell Gas Station"},
            bank_account=bank_account,
        )

        result = converter.convert_import_row_to_transaction(import_data)

        assert result.success is True
        txn = result.transaction
        assert txn.payoree is not None
        assert txn.payoree.name == "Shell Gas Station"

    def test_conversion_failure_missing_required_fields(self):
        """Test conversion failure when required fields are missing."""
        import_data = ImportRowData(
            row_index=1,
            date=None,  # Missing required date
            amount=Decimal("100.00"),
            description="Test transaction",
        )

        result = converter.convert_import_row_to_transaction(import_data)

        assert result.success is False
        assert len(result.errors) > 0
        assert "Missing required date or amount" in result.errors[0]
        assert result.row_index == 1

    def test_conversion_handles_category_errors_gracefully(self):
        """Test that conversion handles category lookup errors gracefully."""
        bank_account = FinancialAccount.objects.create(
            name="test_bank",
            column_map={
                "Date": "date",
                "Amount": "amount",
                "Description": "description",
            },
        )

        import_data = ImportRowData(
            row_index=1,
            date=date(2024, 1, 15),
            amount=Decimal("25.00"),
            description="Unknown category transaction",
            suggestions={"subcategory": "NonexistentCategory"},
            bank_account=bank_account,
        )

        result = converter.convert_import_row_to_transaction(import_data)

        # Should still succeed but with categorization error
        assert result.success is True
        txn = result.transaction
        assert txn.categorization_error is not None
        assert txn.category is None
        assert txn.subcategory is None
