import pytest
import io
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import Mock, patch

from ingest.models import ImportBatch, ImportRow, FinancialAccount
from ingest.forms import UploadCSVForm


@pytest.mark.django_db
class TestUploadCSVView(TestCase):
    def setUp(self):
        self.client = Client()
        self.upload_url = reverse("ingest:batch_upload")
        self.user = User.objects.create_user(username="testuser", password="testpass")

    def test_upload_view_get_renders_form(self):
        """GET request should render upload form"""
        response = self.client.get(self.upload_url)

        assert response.status_code == 200
        assert "form" in response.context
        assert isinstance(response.context["form"], UploadCSVForm)
        assert "ingest/upload_form.html" in [t.name for t in response.templates]

    def test_upload_view_post_valid_csv_creates_batch(self):
        """POST with valid CSV should create batch and redirect to preview"""
        csv_content = "Date,Description,Amount\n2023-01-01,Test Transaction,-50.00\n"
        csv_file = SimpleUploadedFile(
            "test.csv", csv_content.encode("utf-8"), content_type="text/csv"
        )

        response = self.client.post(self.upload_url, {"file": csv_file})

        # Should redirect to preview
        assert response.status_code == 302

        # Should create a batch
        batch = ImportBatch.objects.first()
        assert batch is not None
        assert batch.source_filename == "test.csv"
        assert batch.row_count == 1

        # Should redirect to correct preview URL
        expected_url = reverse("ingest:batch_preview", kwargs={"pk": batch.pk})
        assert response.url == expected_url

        # Should show success message
        messages = list(get_messages(response.wsgi_request))
        assert len(messages) == 1
        assert "Uploaded 1 rows" in str(messages[0])

    def test_upload_view_post_authenticated_user_sets_user(self):
        """POST by authenticated user should set user on batch"""
        self.client.login(username="testuser", password="testpass")

        csv_content = "Date,Description,Amount\n2023-01-01,Test Transaction,-50.00\n"
        csv_file = SimpleUploadedFile(
            "test.csv", csv_content.encode("utf-8"), content_type="text/csv"
        )

        response = self.client.post(self.upload_url, {"file": csv_file})

        batch = ImportBatch.objects.first()
        assert batch.created_by == self.user

    def test_upload_view_post_with_profile_assigns_profile(self):
        """POST with profile selection should assign profile to batch"""
        profile = FinancialAccount.objects.create(
            name="Test Profile",
            column_map={
                "Date": "date",
                "Description": "description",
                "Amount": "amount",
            },
        )

        csv_content = "Date,Description,Amount\n2023-01-01,Test Transaction,-50.00\n"
        csv_file = SimpleUploadedFile(
            "test.csv", csv_content.encode("utf-8"), content_type="text/csv"
        )

        response = self.client.post(
            self.upload_url, {"file": csv_file, "profile": profile.pk}
        )

        batch = ImportBatch.objects.first()
        assert batch.profile == profile

    def test_upload_view_post_invalid_form_shows_errors(self):
        """POST with invalid form should show form errors"""
        response = self.client.post(self.upload_url, {})

        assert response.status_code == 200
        assert "form" in response.context
        assert response.context["form"].errors
        assert "file" in response.context["form"].errors

    def test_upload_view_post_empty_csv_creates_batch_with_zero_rows(self):
        """POST with empty CSV should create batch with zero rows"""
        csv_content = "Date,Description,Amount\n"  # Header only
        csv_file = SimpleUploadedFile(
            "empty.csv", csv_content.encode("utf-8"), content_type="text/csv"
        )

        response = self.client.post(self.upload_url, {"file": csv_file})

        batch = ImportBatch.objects.first()
        assert batch.row_count == 0

        messages = list(get_messages(response.wsgi_request))
        assert "Uploaded 0 rows" in str(messages[0])


@pytest.mark.django_db
class TestBatchPreviewView(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="testpass")

        # Create test batch with rows
        self.batch = ImportBatch.objects.create(
            source_filename="test.csv",
            header=["Date", "Description", "Amount"],
            row_count=2,
        )

        self.row1 = ImportRow.objects.create(
            batch=self.batch,
            row_index=0,
            raw={"Date": "2023-01-01", "Description": "Coffee Shop", "Amount": "-5.50"},
        )
        self.row2 = ImportRow.objects.create(
            batch=self.batch,
            row_index=1,
            raw={
                "Date": "2023-01-02",
                "Description": "Gas Station",
                "Amount": "-45.00",
            },
        )

        self.preview_url = reverse("ingest:batch_preview", kwargs={"pk": self.batch.pk})

    def test_preview_view_get_renders_template(self):
        """GET request should render preview template"""
        response = self.client.get(self.preview_url)

        assert response.status_code == 200
        assert "batch" in response.context
        assert response.context["batch"] == self.batch
        assert "ingest/preview.html" in [t.name for t in response.templates]

    def test_preview_view_batch_without_profile_shows_missing_profile(self):
        """Batch without profile should show missing profile context"""
        response = self.client.get(self.preview_url)

        assert response.context["missing_profile"] is True
        assert "csv_headers" in response.context
        assert response.context["csv_headers"] == ["Date", "Description", "Amount"]
        assert "available_profiles" in response.context

    def test_preview_view_auto_matches_exact_profile(self):
        """View should auto-match profile with exact header match"""
        profile = FinancialAccount.objects.create(
            name="Exact Match Profile",
            column_map={
                "Date": "date",
                "Description": "description",
                "Amount": "amount",
            },
        )

        with patch("ingest.views.views.apply_profile_to_batch") as mock_apply:
            mock_apply.return_value = (2, 0)  # 2 updated, 0 duplicates

            response = self.client.get(self.preview_url)

            self.batch.refresh_from_db()
            assert self.batch.profile == profile

            mock_apply.assert_called_once_with(self.batch, profile)

            messages = list(get_messages(response.wsgi_request))
            assert any(
                "Automatically matched and processed" in str(m) for m in messages
            )

    def test_preview_view_auto_matches_subset_profile(self):
        """View should auto-match profile that is subset of CSV headers"""
        profile = FinancialAccount.objects.create(
            name="Subset Profile",
            column_map={
                "Date": "date",
                "Amount": "amount",  # Missing Description - subset of CSV
            },
        )

        with patch("ingest.views.views.apply_profile_to_batch") as mock_apply:
            mock_apply.return_value = (2, 1)  # 2 updated, 1 duplicate

            response = self.client.get(self.preview_url)

            self.batch.refresh_from_db()
            assert self.batch.profile == profile

            messages = list(get_messages(response.wsgi_request))
            assert any("ignoring extra CSV columns" in str(m) for m in messages)

    def test_preview_view_with_profile_shows_mapping_table(self):
        """View with assigned profile should show mapping table"""
        profile = FinancialAccount.objects.create(
            name="Test Profile",
            column_map={
                "Date": "date",
                "Description": "description",
                "Amount": "amount",
            },
        )
        self.batch.profile = profile
        self.batch.save()

        response = self.client.get(self.preview_url)

        assert "missing_profile" not in response.context
        assert "mapping_table" in response.context
        assert "profile" in response.context
        assert response.context["profile"] == profile

        # Check mapping table structure
        mapping_table = response.context["mapping_table"]
        assert len(mapping_table) > 0

        # Check for expected field mappings
        date_mapping = next(
            (m for m in mapping_table if m["txn_field"] == "date"), None
        )
        assert date_mapping is not None
        assert date_mapping["csv_field"] == "Date"
        assert date_mapping["sample_value"] == "2023-01-01"

    def test_preview_view_post_method_allowed(self):
        """POST request should be allowed and return same content as GET"""
        response = self.client.post(self.preview_url)

        assert response.status_code == 200
        assert "batch" in response.context

    def test_preview_view_nonexistent_batch_returns_404(self):
        """Request for nonexistent batch should return 404"""
        nonexistent_url = reverse("ingest:batch_preview", kwargs={"pk": 999})
        response = self.client.get(nonexistent_url)

        assert response.status_code == 404


@pytest.mark.django_db
class TestApplyProfileView(TestCase):
    def setUp(self):
        self.client = Client()

        self.batch = ImportBatch.objects.create(
            source_filename="test.csv",
            header=["Date", "Description", "Amount"],
            row_count=1,
        )

        self.profile = FinancialAccount.objects.create(
            name="Test Profile",
            column_map={
                "Date": "date",
                "Description": "description",
                "Amount": "amount",
            },
        )

        self.apply_url = reverse(
            "ingest:batch_apply_profile", kwargs={"pk": self.batch.pk}
        )

    def test_apply_profile_assigns_profile_and_processes_batch(self):
        """POST should assign profile and process batch"""
        with patch("ingest.views.views.apply_profile_to_batch") as mock_apply:
            mock_apply.return_value = (1, 0)  # 1 updated, 0 duplicates

            response = self.client.post(self.apply_url, {"profile_id": self.profile.pk})

            # Should redirect to preview
            assert response.status_code == 302
            expected_url = reverse("ingest:batch_preview", kwargs={"pk": self.batch.pk})
            assert response.url == expected_url

            # Should call apply_profile_to_batch
            mock_apply.assert_called_once_with(
                self.batch, self.profile, bank_account_hint=None
            )

            messages = list(get_messages(response.wsgi_request))
            assert any("Mapped 1 rows" in str(m) for m in messages)

    def test_apply_profile_with_bank_account_hint(self):
        """POST with bank_account should pass hint to service"""
        with patch("ingest.views.views.apply_profile_to_batch") as mock_apply:
            mock_apply.return_value = (1, 0)

            response = self.client.post(
                self.apply_url,
                {"profile_id": self.profile.pk, "bank_account": "Chase Checking"},
            )

            mock_apply.assert_called_once_with(
                self.batch, self.profile, bank_account_hint="Chase Checking"
            )

    def test_apply_profile_nonexistent_batch_returns_404(self):
        """Request for nonexistent batch should return 404"""
        nonexistent_url = reverse("ingest:batch_apply_profile", kwargs={"pk": 999})
        response = self.client.post(nonexistent_url, {"profile_id": self.profile.pk})

        assert response.status_code == 404

    def test_apply_profile_nonexistent_profile_returns_404(self):
        """Request with nonexistent profile should return 404"""
        response = self.client.post(self.apply_url, {"profile_id": 999})

        assert response.status_code == 404


@pytest.mark.django_db
class TestCommitView(TestCase):
    def setUp(self):
        self.client = Client()

        self.batch = ImportBatch.objects.create(
            source_filename="test.csv",
            header=["Date", "Description", "Amount"],
            row_count=1,
            status="mapped",
        )

        self.commit_url = reverse("ingest:batch_commit", kwargs={"pk": self.batch.pk})

    def test_commit_view_get_redirects_to_preview(self):
        """GET request should redirect to preview"""
        response = self.client.get(self.commit_url)

        assert response.status_code == 302
        expected_url = reverse("ingest:batch_preview", kwargs={"pk": self.batch.pk})
        assert response.url == expected_url

    def test_commit_view_post_without_bank_account_shows_error(self):
        """POST without bank_account should show error and redirect"""
        response = self.client.post(self.commit_url, {})

        assert response.status_code == 302

        messages = list(get_messages(response.wsgi_request))
        assert any("Bank account is required" in str(m) for m in messages)

    def test_commit_view_post_with_bank_account_commits_batch(self):
        """POST with bank_account should commit batch"""
        with patch("ingest.views.views.commit_batch") as mock_commit:
            mock_commit.return_value = (
                [1],
                [2],
                [],
            )  # 1 imported, 1 duplicate, 0 skipped

            response = self.client.post(
                self.commit_url, {"bank_account": "Chase Checking"}
            )

            # Should redirect to transactions list
            assert response.status_code == 302
            assert response.url == reverse("transactions:transactions_list")

            # Should call commit_batch
            mock_commit.assert_called_once_with(
                self.batch, "Chase Checking", reverse_amounts=False
            )

            messages = list(get_messages(response.wsgi_request))
            assert any("Imported 1 transactions" in str(m) for m in messages)

    def test_commit_view_nonexistent_batch_returns_404(self):
        """Request for nonexistent batch should return 404"""
        nonexistent_url = reverse("ingest:batch_commit", kwargs={"pk": 999})
        response = self.client.post(nonexistent_url, {"bank_account": "Test Account"})

        assert response.status_code == 404


@pytest.mark.django_db
class TestBatchListView(TestCase):
    def setUp(self):
        self.client = Client()
        self.list_url = reverse("ingest:batch_list")

    def test_batch_list_view_renders_template(self):
        """GET request should render batch list template"""
        response = self.client.get(self.list_url)

        assert response.status_code == 200
        assert "batches" in response.context
        assert "ingest/batch_list.html" in [t.name for t in response.templates]

    def test_batch_list_view_shows_batches(self):
        """View should display created batches"""
        batch1 = ImportBatch.objects.create(source_filename="test1.csv", row_count=5)
        batch2 = ImportBatch.objects.create(source_filename="test2.csv", row_count=3)

        response = self.client.get(self.list_url)

        batches = response.context["batches"]
        assert batch1 in batches
        assert batch2 in batches

    def test_batch_list_view_pagination(self):
        """View should paginate results"""
        # Create more than 20 batches to test pagination
        for i in range(25):
            ImportBatch.objects.create(source_filename=f"test{i}.csv", row_count=1)

        response = self.client.get(self.list_url)

        assert response.context["is_paginated"] is True
        assert len(response.context["batches"]) == 20


@pytest.mark.django_db
class TestFinancialAccountViews(TestCase):
    def setUp(self):
        self.client = Client()

        self.profile = FinancialAccount.objects.create(
            name="Test Profile",
            description="Test description",
            column_map={"Date": "date", "Amount": "amount"},
        )

    def test_profile_list_view_renders_template(self):
        """Profile list view should render template"""
        url = reverse("ingest:profile_list")
        response = self.client.get(url)

        assert response.status_code == 200
        assert "profiles" in response.context
        assert self.profile in response.context["profiles"]
        assert "ingest/profile_list.html" in [t.name for t in response.templates]

    def test_profile_detail_view_renders_template(self):
        """Profile detail view should render template"""
        url = reverse("ingest:profile_detail", kwargs={"pk": self.profile.pk})
        response = self.client.get(url)

        assert response.status_code == 200
        assert "profile" in response.context
        assert response.context["profile"] == self.profile
        assert "ingest/profile_detail.html" in [t.name for t in response.templates]

    def test_profile_detail_view_nonexistent_profile_returns_404(self):
        """Profile detail view for nonexistent profile should return 404"""
        url = reverse("ingest:profile_detail", kwargs={"pk": 999})
        response = self.client.get(url)

        assert response.status_code == 404


@pytest.mark.django_db
class TestViewIntegration(TestCase):
    """Integration tests for the complete CSV upload workflow"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="testpass")

    def test_complete_csv_upload_workflow(self):
        """Test complete workflow: upload -> auto-match profile -> commit"""
        # Step 1: Create matching profile
        profile = FinancialAccount.objects.create(
            name="Bank Profile",
            column_map={
                "Date": "date",
                "Description": "description",
                "Amount": "amount",
            },
        )

        # Step 2: Upload CSV
        csv_content = "Date,Description,Amount\n2023-01-01,Coffee Shop,-5.50\n"
        csv_file = SimpleUploadedFile(
            "bank.csv", csv_content.encode("utf-8"), content_type="text/csv"
        )

        upload_url = reverse("ingest:batch_upload")
        response = self.client.post(upload_url, {"file": csv_file})

        # Should redirect to preview
        assert response.status_code == 302

        batch = ImportBatch.objects.first()
        preview_url = reverse("ingest:batch_preview", kwargs={"pk": batch.pk})

        # Step 3: View preview (should auto-match profile)
        with patch("ingest.views.views.apply_profile_to_batch") as mock_apply:
            mock_apply.return_value = (1, 0)

            response = self.client.get(preview_url)

            batch.refresh_from_db()
            assert batch.profile == profile

        # Step 4: Commit batch
        commit_url = reverse("ingest:batch_commit", kwargs={"pk": batch.pk})

        with patch("ingest.views.views.commit_batch") as mock_commit:
            mock_commit.return_value = ([1], [], [])

            response = self.client.post(commit_url, {"bank_account": "Test Account"})

            assert response.status_code == 302
            assert response.url == reverse("transactions:transactions_list")

    def test_workflow_with_manual_profile_selection(self):
        """Test workflow when no auto-match occurs"""
        # Create profile that won't auto-match
        profile = FinancialAccount.objects.create(
            name="Different Profile",
            column_map={
                "TransactionDate": "date",  # Different header names
                "Memo": "description",
                "Debit": "amount",
            },
        )

        # Upload CSV with different headers
        csv_content = "Date,Description,Amount\n2023-01-01,Coffee Shop,-5.50\n"
        csv_file = SimpleUploadedFile(
            "bank.csv", csv_content.encode("utf-8"), content_type="text/csv"
        )

        upload_url = reverse("ingest:batch_upload")
        response = self.client.post(upload_url, {"file": csv_file})

        batch = ImportBatch.objects.first()
        preview_url = reverse("ingest:batch_preview", kwargs={"pk": batch.pk})

        # Preview should show missing profile
        response = self.client.get(preview_url)
        assert response.context["missing_profile"] is True

        # Manually apply profile
        apply_url = reverse("ingest:batch_apply_profile", kwargs={"pk": batch.pk})

        with patch("ingest.views.apply_profile_to_batch") as mock_apply:
            mock_apply.return_value = (1, 0)

            response = self.client.post(apply_url, {"profile_id": profile.pk})

            assert response.status_code == 302
