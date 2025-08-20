"""
Comprehensive test suite for ingest models.

Tests the core data models that handle CSV import pipeline:
- MappingProfile: Column mapping configurations for different bank formats
- ImportBatch: Batch processing with status management (uploaded→previewed→committed)
- ImportRow: Individual transaction rows with normalization and AI suggestions

Coverage: Model validation, relationships, state transitions, error handling
"""
import pytest
from decimal import Decimal
from datetime import date, datetime
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.contrib.auth import get_user_model

from ingest.models import MappingProfile, ImportBatch, ImportRow

User = get_user_model()
pytestmark = pytest.mark.django_db


class TestMappingProfile:
    """Test mapping profile model for CSV column configurations."""
    
    def test_create_basic_profile(self):
        """Test creating a basic mapping profile."""
        profile = MappingProfile.objects.create(
            name="chase_checking",
            column_map={
                "Posting Date": "date",
                "Description": "description", 
                "Amount": "amount"
            },
            description="Chase Bank checking account format"
        )
        
        assert profile.name == "chase_checking"
        assert profile.column_map["Posting Date"] == "date"
        assert "Chase Bank" in profile.description
    
    def test_profile_name_must_be_unique(self):
        """Test that profile names must be unique."""
        MappingProfile.objects.create(name="chase", column_map={})
        
        with pytest.raises(IntegrityError):
            MappingProfile.objects.create(name="chase", column_map={})
    
    def test_profile_with_options(self):
        """Test profile with additional options."""
        profile = MappingProfile.objects.create(
            name="visa_card",
            column_map={"Date": "date", "Amount": "amount"},
            options={
                "date_format": "%m/%d/%Y",
                "amount_sign": "negative_is_expense"
            }
        )
        
        assert profile.options["date_format"] == "%m/%d/%Y"
        assert profile.options["amount_sign"] == "negative_is_expense"
    
    def test_profile_str_representation(self):
        """Test string representation uses description."""
        profile = MappingProfile.objects.create(
            name="test",
            column_map={},
            description="Test Bank Account Format"
        )
        
        assert str(profile) == "Test Bank Account Format"
    
    def test_profile_empty_description_fallback(self):
        """Test string representation when description is empty."""
        profile = MappingProfile.objects.create(
            name="test",
            column_map={}
        )
        
        # Should handle empty description gracefully
        assert str(profile) == ""


class TestImportBatch:
    """Test import batch model for CSV upload batches."""
    
    def test_create_basic_batch(self):
        """Test creating a basic import batch."""
        batch = ImportBatch.objects.create(
            source_filename="test.csv",
            header=["Date", "Description", "Amount"],
            row_count=10
        )
        
        assert batch.source_filename == "test.csv"
        assert batch.header == ["Date", "Description", "Amount"]
        assert batch.row_count == 10
        assert batch.status == "uploaded"  # Default status
    
    def test_batch_with_user(self):
        """Test batch creation with user assignment."""
        user = User.objects.create_user(username="testuser", email="test@example.com")
        batch = ImportBatch.objects.create(
            created_by=user,
            source_filename="user_upload.csv",
            header=["Date", "Amount"],
            row_count=5
        )
        
        assert batch.created_by == user
        assert batch.source_filename == "user_upload.csv"
    
    def test_batch_with_profile(self):
        """Test batch with assigned mapping profile."""
        profile = MappingProfile.objects.create(name="test_profile", column_map={})
        batch = ImportBatch.objects.create(
            profile=profile,
            header=["Date", "Amount"],
            row_count=3
        )
        
        assert batch.profile == profile
    
    def test_batch_status_transitions(self):
        """Test valid status transitions."""
        batch = ImportBatch.objects.create(header=[], row_count=0)
        
        # Test status progression
        assert batch.status == "uploaded"
        
        batch.status = "previewed"
        batch.save()
        assert batch.status == "previewed"
        
        batch.status = "committed"
        batch.save() 
        assert batch.status == "committed"
    
    def test_batch_ordering(self):
        """Test that batches are ordered by creation date (newest first)."""
        batch1 = ImportBatch.objects.create(source_filename="first.csv", header=[], row_count=0)
        batch2 = ImportBatch.objects.create(source_filename="second.csv", header=[], row_count=0)
        
        batches = list(ImportBatch.objects.all())
        assert batches[0] == batch2  # Newest first
        assert batches[1] == batch1
    
    def test_batch_str_representation(self):
        """Test string representation includes ID and filename."""
        batch = ImportBatch.objects.create(
            source_filename="my_transactions.csv",
            header=[],
            row_count=0
        )
        
        expected = f"Batch {batch.pk} — my_transactions.csv"
        assert str(batch) == expected
    
    def test_batch_str_unnamed_file(self):
        """Test string representation for unnamed files."""
        batch = ImportBatch.objects.create(header=[], row_count=0)
        
        expected = f"Batch {batch.pk} — unnamed"
        assert str(batch) == expected
    
    def test_batch_user_deletion_handling(self):
        """Test that batch survives user deletion."""
        user = User.objects.create_user(username="testuser")
        batch = ImportBatch.objects.create(created_by=user, header=[], row_count=0)
        
        user.delete()
        batch.refresh_from_db()
        
        assert batch.created_by is None  # SET_NULL behavior
    
    def test_batch_profile_deletion_handling(self):
        """Test that batch survives profile deletion."""
        profile = MappingProfile.objects.create(name="test", column_map={})
        batch = ImportBatch.objects.create(profile=profile, header=[], row_count=0)
        
        profile.delete()
        batch.refresh_from_db()
        
        assert batch.profile is None  # SET_NULL behavior


class TestImportRow:
    """Test import row model for individual CSV rows."""
    
    def test_create_basic_row(self):
        """Test creating a basic import row."""
        batch = ImportBatch.objects.create(header=[], row_count=1)
        row = ImportRow.objects.create(
            batch=batch,
            row_index=0,
            raw={"Date": "1/1/2023", "Amount": "100.00", "Description": "Test"}
        )
        
        assert row.batch == batch
        assert row.row_index == 0
        assert row.raw["Date"] == "1/1/2023"
        assert row.raw["Amount"] == "100.00"
    
    def test_row_with_normalized_data(self):
        """Test row with normalized/parsed data."""
        batch = ImportBatch.objects.create(header=[], row_count=1)
        row = ImportRow.objects.create(
            batch=batch,
            row_index=0,
            raw={"Date": "1/1/2023", "Amount": "100.00"},
            norm_date=date(2023, 1, 1),
            norm_amount=Decimal("100.00"),
            norm_description="Test Transaction"
        )
        
        assert row.norm_date == date(2023, 1, 1)
        assert row.norm_amount == Decimal("100.00")
        assert row.norm_description == "Test Transaction"
    
    def test_row_with_ai_suggestions(self):
        """Test row with AI categorization suggestions."""
        batch = ImportBatch.objects.create(header=[], row_count=1)
        row = ImportRow.objects.create(
            batch=batch,
            row_index=0,
            raw={"Description": "STARBUCKS #1234"},
            suggestions={
                "subcategory": "Coffee/Tea",
                "payoree": "Starbucks"
            }
        )
        
        assert row.suggestions["subcategory"] == "Coffee/Tea"
        assert row.suggestions["payoree"] == "Starbucks"
    
    def test_row_with_errors(self):
        """Test row with parsing errors."""
        batch = ImportBatch.objects.create(header=[], row_count=1)
        row = ImportRow.objects.create(
            batch=batch,
            row_index=0,
            raw={"Date": "invalid", "Amount": "not-a-number"},
            errors=["date: invalid format", "amount: not a valid decimal"]
        )
        
        assert len(row.errors) == 2
        assert "date: invalid format" in row.errors
        assert "amount: not a valid decimal" in row.errors
    
    def test_row_duplicate_flag(self):
        """Test duplicate detection flag."""
        batch = ImportBatch.objects.create(header=[], row_count=1)
        row = ImportRow.objects.create(
            batch=batch,
            row_index=0,
            raw={"Amount": "100.00"},
            is_duplicate=True
        )
        
        assert row.is_duplicate is True
    
    def test_row_unique_constraint(self):
        """Test that batch+row_index must be unique."""
        batch = ImportBatch.objects.create(header=[], row_count=2)
        
        # First row with index 0 should work
        ImportRow.objects.create(batch=batch, row_index=0, raw={})
        
        # Second row with same index should fail
        with pytest.raises(IntegrityError):
            ImportRow.objects.create(batch=batch, row_index=0, raw={})
    
    def test_row_ordering(self):
        """Test that rows are ordered by row_index."""
        batch = ImportBatch.objects.create(header=[], row_count=3)
        
        # Create rows out of order
        row2 = ImportRow.objects.create(batch=batch, row_index=2, raw={})
        row0 = ImportRow.objects.create(batch=batch, row_index=0, raw={})
        row1 = ImportRow.objects.create(batch=batch, row_index=1, raw={})
        
        # Should be ordered by row_index
        rows = list(batch.rows.all())
        assert rows == [row0, row1, row2]
    
    def test_row_str_representation(self):
        """Test string representation includes batch and index."""
        batch = ImportBatch.objects.create(header=[], row_count=1)
        row = ImportRow.objects.create(batch=batch, row_index=5, raw={})
        
        expected = f"ImportRow(batch={batch.id}, idx=5)"
        assert str(row) == expected
    
    def test_row_committed_transaction_tracking(self):
        """Test tracking of committed transaction ID."""
        batch = ImportBatch.objects.create(header=[], row_count=1)
        row = ImportRow.objects.create(
            batch=batch,
            row_index=0,
            raw={},
            committed_txn_id=12345
        )
        
        assert row.committed_txn_id == 12345
    
    def test_row_timestamps(self):
        """Test that timestamps are set correctly."""
        batch = ImportBatch.objects.create(header=[], row_count=1)
        
        before = datetime.now()
        row = ImportRow.objects.create(batch=batch, row_index=0, raw={})
        after = datetime.now()
        
        # created_at should be set
        assert before <= row.created_at.replace(tzinfo=None) <= after
        
        # updated_at should be set initially
        assert before <= row.updated_at.replace(tzinfo=None) <= after


class TestModelRelationships:
    """Test relationships between ingest models."""
    
    def test_batch_rows_relationship(self):
        """Test that batch.rows returns related ImportRows."""
        batch = ImportBatch.objects.create(header=[], row_count=2)
        row1 = ImportRow.objects.create(batch=batch, row_index=0, raw={})
        row2 = ImportRow.objects.create(batch=batch, row_index=1, raw={})
        
        # Should be accessible via reverse relationship
        rows = list(batch.rows.all())
        assert len(rows) == 2
        assert row1 in rows
        assert row2 in rows
    
    def test_batch_deletion_cascades_to_rows(self):
        """Test that deleting batch deletes associated rows."""
        batch = ImportBatch.objects.create(header=[], row_count=1)
        row = ImportRow.objects.create(batch=batch, row_index=0, raw={})
        
        batch.delete()
        
        # Row should be deleted due to CASCADE
        assert not ImportRow.objects.filter(id=row.id).exists()
    
    def test_profile_deletion_sets_null_on_batch(self):
        """Test that deleting profile sets NULL on batches."""
        profile = MappingProfile.objects.create(name="test", column_map={})
        batch = ImportBatch.objects.create(profile=profile, header=[], row_count=0)
        
        profile.delete()
        batch.refresh_from_db()
        
        assert batch.profile is None


class TestModelIndexes:
    """Test that database indexes work correctly for performance."""
    
    def test_batch_status_index(self):
        """Test querying by status (should use index)."""
        # Create batches with different statuses
        ImportBatch.objects.create(status="uploaded", header=[], row_count=0)
        ImportBatch.objects.create(status="previewed", header=[], row_count=0)
        ImportBatch.objects.create(status="committed", header=[], row_count=0)
        
        # Query by status should work efficiently
        uploaded = ImportBatch.objects.filter(status="uploaded")
        assert uploaded.count() == 1
        
        previewed = ImportBatch.objects.filter(status="previewed")
        assert previewed.count() == 1
    
    def test_row_duplicate_index(self):
        """Test querying by duplicate flag (should use index)."""
        batch = ImportBatch.objects.create(header=[], row_count=2)
        ImportRow.objects.create(batch=batch, row_index=0, raw={}, is_duplicate=True)
        ImportRow.objects.create(batch=batch, row_index=1, raw={}, is_duplicate=False)
        
        # Query by duplicate flag should work efficiently
        duplicates = ImportRow.objects.filter(is_duplicate=True)
        assert duplicates.count() == 1
    
    def test_row_date_index(self):
        """Test querying by normalized date (should use index)."""
        batch = ImportBatch.objects.create(header=[], row_count=2)
        ImportRow.objects.create(
            batch=batch, 
            row_index=0, 
            raw={}, 
            norm_date=date(2023, 1, 1)
        )
        ImportRow.objects.create(
            batch=batch, 
            row_index=1, 
            raw={}, 
            norm_date=date(2023, 1, 2)
        )
        
        # Query by date should work efficiently
        jan_first = ImportRow.objects.filter(norm_date=date(2023, 1, 1))
        assert jan_first.count() == 1
