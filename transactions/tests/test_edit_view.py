import pytest
import json
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from transactions.models import Transaction, Category, Payoree
from ingest.models import FinancialAccount
from transactions.forms import TransactionForm


class TransactionEditViewTest(TestCase):
    """Test the transaction edit view with AJAX functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.client.login(username="testuser", password="testpass")

        # Create test data
        self.category = Category.objects.create(name="Test Category")
        self.payoree = Payoree.objects.create(name="Test Payoree")
        self.financial_account = FinancialAccount.objects.create(
            name="Test Account", column_map={}, description="Test Financial Account"
        )

        self.transaction = Transaction.objects.create(
            date="2025-01-01",
            description="Test Transaction",
            amount=-10.00,
            bank_account=self.financial_account,
            payoree=self.payoree,
            category=self.category,
            needs_level={"core": 100},
        )

    def test_edit_view_get_request(self):
        """Test that the edit view renders correctly."""
        url = reverse(
            "transactions:edit_transaction", kwargs={"pk": self.transaction.pk}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Transaction")
        self.assertContains(response, "needs_level")

    def test_edit_view_ajax_post_valid(self):
        """Test AJAX POST request with valid data."""
        url = reverse(
            "transactions:edit_transaction", kwargs={"pk": self.transaction.pk}
        )
        data = {
            "date": "2025-01-02",
            "description": "Updated Transaction",
            "amount": "-15.00",
            "bank_account": self.financial_account.pk,
            "payoree": self.payoree.pk,
            "category": self.category.pk,
            "needs_level": '{"core": 50, "discretionary": 50}',
            "memo": "Updated memo",
        }

        response = self.client.post(
            url, data=data, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data["success"])

        # Refresh transaction from database
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.description, "Updated Transaction")
        self.assertEqual(
            self.transaction.needs_level, {"core": 50, "discretionary": 50}
        )

    def test_edit_view_ajax_post_invalid(self):
        """Test AJAX POST request with invalid data."""
        url = reverse(
            "transactions:edit_transaction", kwargs={"pk": self.transaction.pk}
        )
        data = {
            "date": "",  # Invalid: empty date
            "description": "Updated Transaction",
            "amount": "invalid_amount",  # Invalid: not a number
            "bank_account": self.financial_account.pk,
            "payoree": self.payoree.pk,
            "category": self.category.pk,
            "needs_level": '{"core": 100}',
            "memo": "Updated memo",
        }

        response = self.client.post(
            url, data=data, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertFalse(response_data["success"])
        self.assertIn("date", response_data["errors"])
        self.assertIn("amount", response_data["errors"])

    def test_form_initialization_with_needs_level(self):
        """Test that the form initializes correctly with existing needs_level."""
        form = TransactionForm(instance=self.transaction)
        self.assertEqual(form.initial["needs_level"], {"core": 100})
