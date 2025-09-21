"""
Comprehensive test suite for ingest services.

Tests the core business logic that handles CSV processing pipeline:
- staging.py: CSV file parsing and batch creation
- mapping.py: Profile application, row mapping, duplicate detection, commit process
- helpers.py: Utility functions for CSV processing

Coverage: File processing, profile mapping, AI suggestions, error handling, commit workflow
"""

import pytest
from decimal import Decimal
from datetime import date
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

from ingest.models import FinancialAccount, ImportBatch, ImportRow
from ingest.services.staging import create_batch_from_csv
from ingest.services.mapping import (
    map_row_with_profile,
    apply_profile_to_batch,
    commit_batch,
    _parse_date,
    _json_safe,
)
from transactions.models import Transaction, Category, Payoree
from django.contrib.auth import get_user_model

User = get_user_model()
pytestmark = pytest.mark.django_db


class TestStagingService:
    """Test CSV file processing and batch creation."""

    def test_create_batch_from_csv_basic(self):
        """Test creating batch from simple CSV content."""
        csv_content = "Date,Description,Amount\n1/1/2023,Test Transaction,100.00\n1/2/2023,Another Transaction,-50.00"
        csv_file = StringIO(csv_content)
        csv_file.name = "test.csv"

        batch = create_batch_from_csv(csv_file)

        assert batch.source_filename == "test.csv"
        assert batch.header == ["Date", "Description", "Amount"]
        assert batch.row_count == 2
        assert batch.status == "uploaded"

        # Check rows were created
        rows = list(batch.rows.all())
        assert len(rows) == 2
        assert rows[0].raw["Date"] == "1/1/2023"
        assert rows[0].raw["Description"] == "Test Transaction"
        assert rows[1].raw["Amount"] == "-50.00"

    def test_create_batch_with_user(self):
        """Test creating batch with user assignment."""
        user = User.objects.create_user(username="testuser")
        csv_content = "Date,Amount\n1/1/2023,100.00"
        csv_file = StringIO(csv_content)
        csv_file.name = "user_upload.csv"

        batch = create_batch_from_csv(csv_file, user=user)

        assert batch.created_by == user
        assert batch.source_filename == "user_upload.csv"

    def test_create_batch_with_profile(self):
        """Test creating batch with pre-assigned profile."""
        profile = FinancialAccount.objects.create(name="test_profile", column_map={})
        csv_content = "Date,Amount\n1/1/2023,100.00"
        csv_file = StringIO(csv_content)

        batch = create_batch_from_csv(csv_file, profile=profile)

        assert batch.profile == profile

    def test_create_batch_empty_csv(self):
        """Test creating batch from empty CSV."""
        csv_content = ""
        csv_file = StringIO(csv_content)
        csv_file.name = "empty.csv"

        batch = create_batch_from_csv(csv_file)

        assert batch.row_count == 0
        assert batch.header == []

    def test_create_batch_header_only(self):
        """Test creating batch from CSV with header but no data rows."""
        csv_content = "Date,Description,Amount"  # No newline = no empty row
        csv_file = StringIO(csv_content)
        csv_file.name = "header_only.csv"

        batch = create_batch_from_csv(csv_file)

        assert batch.row_count == 0
        assert batch.header == []  # No data rows means empty header


class TestMappingService:
    """Test profile mapping and row processing."""

    def test_parse_date_various_formats(self):
        """Test date parsing with different formats."""
        # Standard formats
        assert _parse_date("1/1/2023") == date(2023, 1, 1)
        assert _parse_date("01/01/2023") == date(2023, 1, 1)
        assert _parse_date("2023-01-01") == date(2023, 1, 1)

        # Invalid dates should raise exception
        with pytest.raises(ValueError):
            _parse_date("invalid-date")

    def test_json_safe_conversion(self):
        """Test that values are converted to JSON-safe formats."""
        # Test different data types
        test_date = date(2023, 1, 1)
        test_decimal = Decimal("100.50")

        assert _json_safe(test_date) == "2023-01-01"
        assert _json_safe(test_decimal) == 100.5
        assert _json_safe("string") == "string"
        assert _json_safe(123) == 123

    def test_map_row_basic_mapping(self):
        """Test basic row mapping with simple profile."""
        profile = FinancialAccount.objects.create(
            name="basic",
            column_map={
                "Date": "date",
                "Description": "description",
                "Amount": "amount",
            },
        )

        raw_row = {
            "Date": "1/1/2023",
            "Description": "Test Transaction",
            "Amount": "100.00",
        }

        result = map_row_with_profile(raw_row, profile)

        assert result["date"] == "1/1/2023"
        assert result["_date"] == date(2023, 1, 1)
        assert result["description"] == "Test Transaction"
        assert result["amount"] == "100.00"
        assert result["_amount"] == Decimal("100.00")

    def test_map_row_with_errors(self):
        """Test row mapping with invalid data."""
        profile = FinancialAccount.objects.create(
            name="basic", column_map={"Date": "date", "Amount": "amount"}
        )

        raw_row = {"Date": "invalid-date", "Amount": "not-a-number"}

        result = map_row_with_profile(raw_row, profile)

        # Should capture errors
        assert len(result["_errors"]) == 2
        assert any("date:" in error for error in result["_errors"])
        assert any("amount:" in error for error in result["_errors"])

    @patch("ingest.services.mapping.suggest_subcategory")
    @patch("ingest.services.mapping.suggest_payoree")
    def test_map_row_with_ai_suggestions(
        self, mock_suggest_payoree, mock_suggest_subcategory
    ):
        """Test that AI suggestions are generated during mapping."""
        mock_suggest_subcategory.return_value = "Coffee/Tea"
        mock_suggest_payoree.return_value = "Starbucks"

        profile = FinancialAccount.objects.create(
            name="basic", column_map={"Description": "description"}
        )

        raw_row = {"Description": "STARBUCKS #1234"}

        result = map_row_with_profile(raw_row, profile)

        assert result["_suggestions"]["subcategory"] == "Coffee/Tea"
        assert result["_suggestions"]["payoree"] == "Starbucks"

        # Verify AI functions were called with the description
        mock_suggest_subcategory.assert_called_once_with("STARBUCKS #1234")
        mock_suggest_payoree.assert_called_once_with("STARBUCKS #1234")

    def test_apply_profile_to_batch_basic(self):
        """Test applying profile to entire batch."""
        # Create test data
        profile = FinancialAccount.objects.create(
            name="test",
            column_map={
                "Date": "date",
                "Description": "description",
                "Amount": "amount",
            },
        )

        batch = ImportBatch.objects.create(header=[], row_count=2)
        ImportRow.objects.create(
            batch=batch,
            row_index=0,
            raw={
                "Date": "1/1/2023",
                "Description": "Transaction 1",
                "Amount": "100.00",
            },
        )
        ImportRow.objects.create(
            batch=batch,
            row_index=1,
            raw={
                "Date": "1/2/2023",
                "Description": "Transaction 2",
                "Amount": "-50.00",
            },
        )

        updated, dup_count = apply_profile_to_batch(batch, profile)

        # Check results
        assert updated == 2
        assert dup_count == 0  # No duplicates by default

        # Check batch was updated
        batch.refresh_from_db()
        assert batch.profile == profile
        assert batch.status == "previewed"

        # Check rows were processed
        rows = list(batch.rows.all())
        assert rows[0].norm_date == date(2023, 1, 1)
        assert rows[0].norm_amount == Decimal("100.00")
        assert rows[0].norm_description == "Transaction 1"
        assert not rows[0].is_duplicate

    @patch("ingest.services.mapping.is_duplicate")
    def test_apply_profile_duplicate_detection(self, mock_is_duplicate):
        """Test duplicate detection during profile application."""
        mock_is_duplicate.return_value = True  # Simulate duplicate found

        profile = FinancialAccount.objects.create(
            name="test", column_map={"Date": "date", "Amount": "amount"}
        )

        batch = ImportBatch.objects.create(header=[], row_count=1)
        ImportRow.objects.create(
            batch=batch, row_index=0, raw={"Date": "1/1/2023", "Amount": "100.00"}
        )

        updated, dup_count = apply_profile_to_batch(batch, profile)

        assert dup_count == 1  # One duplicate detected

        # Check row was marked as duplicate
        row = batch.rows.first()
        assert row.is_duplicate is True

    def test_apply_profile_error_handling(self):
        """Test that profile application handles individual row errors gracefully."""
        profile = FinancialAccount.objects.create(
            name="test", column_map={"Date": "date", "Amount": "amount"}
        )

        batch = ImportBatch.objects.create(header=[], row_count=2)
        # One good row, one bad row
        ImportRow.objects.create(
            batch=batch, row_index=0, raw={"Date": "1/1/2023", "Amount": "100.00"}
        )
        ImportRow.objects.create(
            batch=batch, row_index=1, raw={"Date": "invalid", "Amount": "not-a-number"}
        )

        updated, dup_count = apply_profile_to_batch(batch, profile)

        # Should process both rows despite errors
        assert updated == 2

        # Check error row has errors recorded
        error_row = batch.rows.get(row_index=1)
        assert len(error_row.errors) > 0


class TestCommitService:
    """Test transaction commit process."""

    def test_commit_batch_basic(self):
        """Test basic batch commit to transactions."""
        # Set up test data
        batch = ImportBatch.objects.create(header=[], row_count=2, status="previewed")

        ImportRow.objects.create(
            batch=batch,
            row_index=0,
            norm_date=date(2023, 1, 1),
            norm_amount=Decimal("100.00"),
            norm_description="Test Transaction 1",
        )
        ImportRow.objects.create(
            batch=batch,
            row_index=1,
            norm_date=date(2023, 1, 2),
            norm_amount=Decimal("-50.00"),
            norm_description="Test Transaction 2",
        )

        imported, duplicates, skipped = commit_batch(batch, "Test Bank Account")

        # Check results
        assert len(imported) == 2
        assert len(duplicates) == 0
        assert len(skipped) == 0

        # Check transactions were created
        transactions = Transaction.objects.filter(source__startswith="batch:")
        assert transactions.count() == 2

        # Check batch status updated
        batch.refresh_from_db()
        assert batch.status == "committed"

    def test_commit_batch_with_duplicates(self):
        """Test commit process skips duplicate rows."""
        batch = ImportBatch.objects.create(header=[], row_count=1, status="previewed")

        # Create a row marked as duplicate
        ImportRow.objects.create(
            batch=batch,
            row_index=0,
            norm_date=date(2023, 1, 1),
            norm_amount=Decimal("100.00"),
            norm_description="Duplicate Transaction",
            is_duplicate=True,
        )

        imported, duplicates, skipped = commit_batch(batch, "Test Bank")

        # Duplicate should be skipped
        assert len(imported) == 0
        assert len(duplicates) == 1
        assert len(skipped) == 0

    def test_commit_batch_with_errors(self):
        """Test commit process skips rows with errors."""
        batch = ImportBatch.objects.create(header=[], row_count=1, status="previewed")

        # Create a row with errors
        ImportRow.objects.create(
            batch=batch,
            row_index=0,
            norm_date=None,  # Missing required data
            norm_amount=None,
            norm_description="",
            errors=["date: invalid format", "amount: missing"],
        )

        imported, duplicates, skipped = commit_batch(batch, "Test Bank")

        # Row with errors should be skipped
        assert len(imported) == 0
        assert len(duplicates) == 0
        assert len(skipped) == 1

    def test_commit_batch_with_ai_suggestions(self):
        """Test commit process resolves AI suggestions to foreign keys."""
        # Create test categories and payorees
        food_category = Category.objects.create(name="Food & Dining", type="expense")
        coffee_subcat = Category.objects.create(name="Coffee/Tea", parent=food_category)
        starbucks_payoree = Payoree.objects.create(name="Starbucks")

        batch = ImportBatch.objects.create(header=[], row_count=1, status="previewed")

        ImportRow.objects.create(
            batch=batch,
            row_index=0,
            norm_date=date(2023, 1, 1),
            norm_amount=Decimal("-5.75"),
            norm_description="STARBUCKS #1234",
            suggestions={"subcategory": "Coffee/Tea", "payoree": "Starbucks"},
        )

        imported, duplicates, skipped = commit_batch(batch, "Credit Card")

        # Check results - imported contains row indices, not transaction IDs
        assert len(imported) == 1
        assert imported[0] == 0  # Row index 0 was imported

        # Check transaction was created with resolved FKs
        transaction = Transaction.objects.first()
        assert transaction is not None
        assert transaction.subcategory == coffee_subcat
        assert transaction.payoree == starbucks_payoree

    def test_commit_batch_suggestion_resolution_errors(self):
        """Test commit process handles FK resolution errors gracefully."""
        batch = ImportBatch.objects.create(header=[], row_count=1, status="previewed")

        ImportRow.objects.create(
            batch=batch,
            row_index=0,
            norm_date=date(2023, 1, 1),
            norm_amount=Decimal("100.00"),
            norm_description="Test Transaction",
            suggestions={
                "subcategory": "NonExistentCategory",  # This won't resolve
                "payoree": "NonExistentPayoree",  # This will be created as new
            },
        )

        imported, duplicates, skipped = commit_batch(batch, "Test Bank")

        # Transaction should still be created, just without the unresolved FKs
        assert len(imported) == 1
        assert imported[0] == 0  # Row index 0 was imported

        # Check transaction was created with appropriate resolution behavior
        transaction = Transaction.objects.first()
        assert transaction is not None
        assert transaction.subcategory is None  # Category didn't resolve
        assert transaction.payoree is not None  # Payoree was created
        assert transaction.payoree.name == "NonExistentPayoree"  # New payoree created
        assert transaction.description == "Test Transaction"

    def test_commit_batch_tracks_transaction_ids(self):
        """Test that commit process tracks created transaction IDs on rows."""
        batch = ImportBatch.objects.create(header=[], row_count=1, status="previewed")

        row = ImportRow.objects.create(
            batch=batch,
            row_index=0,
            norm_date=date(2023, 1, 1),
            norm_amount=Decimal("100.00"),
            norm_description="Test Transaction",
        )

        imported, duplicates, skipped = commit_batch(batch, "Test Bank")

        # Check transaction ID was recorded on row - it stores the actual transaction ID
        row.refresh_from_db()
        assert row.committed_txn_id is not None

        # imported contains row indices, not transaction IDs
        assert imported[0] == 0  # Row index 0

        # But the actual transaction ID is stored on the row
        created_transaction = Transaction.objects.get(id=row.committed_txn_id)
        assert created_transaction.description == "Test Transaction"


class TestIntegrationScenarios:
    """Test complete workflows combining multiple services."""

    def test_full_csv_import_workflow(self):
        """Test complete workflow from CSV upload to committed transactions."""
        # Step 1: Create batch from CSV
        csv_content = "Date,Description,Amount\n1/1/2023,STARBUCKS #1234,-5.75\n1/2/2023,SALARY DEPOSIT,2000.00"
        csv_file = StringIO(csv_content)
        csv_file.name = "test_transactions.csv"

        batch = create_batch_from_csv(csv_file)
        assert batch.status == "uploaded"
        assert batch.row_count == 2

        # Step 2: Apply mapping profile
        profile = FinancialAccount.objects.create(
            name="standard",
            column_map={
                "Date": "date",
                "Description": "description",
                "Amount": "amount",
            },
        )

        with patch("ingest.services.mapping.suggest_subcategory") as mock_subcat, patch(
            "ingest.services.mapping.suggest_payoree"
        ) as mock_payoree:
            # Provide enough mock values for all calls
            mock_subcat.return_value = (
                "Coffee/Tea"  # Use return_value instead of side_effect
            )
            mock_payoree.return_value = "Starbucks"

            updated, dup_count = apply_profile_to_batch(batch, profile)

        assert updated == 2
        assert dup_count == 0
        batch.refresh_from_db()
        assert batch.status == "previewed"

        # Step 3: Commit to transactions
        imported, duplicates, skipped = commit_batch(batch, "Chase Checking")

        assert len(imported) == 2
        assert len(duplicates) == 0
        assert len(skipped) == 0
        batch.refresh_from_db()
        assert batch.status == "committed"

        # Verify final transactions
        transactions = Transaction.objects.filter(bank_account__name="Chase Checking")
        assert transactions.count() == 2

        starbucks_txn = transactions.get(description="STARBUCKS #1234")
        assert starbucks_txn.amount == Decimal("-5.75")
        assert starbucks_txn.date == date(2023, 1, 1)

    @patch("ingest.services.mapping.is_duplicate")
    def test_workflow_with_duplicates_and_errors(self, mock_is_duplicate):
        """Test workflow handling duplicates and parsing errors."""
        mock_is_duplicate.side_effect = [
            False,
            True,
            False,
        ]  # Provide enough values for all calls

        # CSV with one good row, one duplicate, one error
        csv_content = "Date,Description,Amount\n1/1/2023,Good Transaction,100.00\n1/2/2023,Duplicate Transaction,50.00\ninvalid-date,Error Transaction,not-a-number"
        csv_file = StringIO(csv_content)
        csv_file.name = "mixed_data.csv"

        batch = create_batch_from_csv(csv_file)

        profile = FinancialAccount.objects.create(
            name="standard",
            column_map={
                "Date": "date",
                "Description": "description",
                "Amount": "amount",
            },
        )

        # Apply profile
        updated, dup_count = apply_profile_to_batch(batch, profile)
        assert updated == 3  # All rows processed
        assert dup_count == 1  # One duplicate detected

        # Commit
        imported, duplicates, skipped = commit_batch(batch, "Test Bank")

        # Only good transaction should be imported
        assert len(imported) == 1
        assert len(duplicates) == 1  # Duplicate skipped
        assert len(skipped) == 1  # Error row skipped

        # Verify only good transaction was created
        assert Transaction.objects.count() == 1
        good_txn = Transaction.objects.first()
        assert good_txn is not None
        assert good_txn.description == "Good Transaction"
