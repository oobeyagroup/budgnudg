"""
Tests for Budget Allocation Deletion Views

These tests verify the view layer functionality for budget allocation deletion.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.messages import get_messages
from decimal import Decimal
from datetime import date
import json

from budgets.models import BudgetPlan, BudgetAllocation
from transactions.models import Category, Payoree, Transaction


class TestAllocationDeletionViews(TestCase):
    """Test the allocation deletion view functionality."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create test categories
        self.groceries_category = Category.objects.create(
            name="Groceries", type="expense"
        )
        self.utilities_category = Category.objects.create(
            name="Utilities", type="expense"
        )

        # Create test payorees
        self.grocery_store = Payoree.objects.create(
            name="Test Grocery Store",
            default_category=self.groceries_category,
        )
        self.utility_company = Payoree.objects.create(
            name="Electric Company",
            default_category=self.utilities_category,
        )

        # Create test budget plan
        self.budget_plan = BudgetPlan.objects.create(
            name="Test Budget", year=2025, month=10, is_active=True
        )

        # Create test allocations
        self.allocation1 = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan,
            payoree=self.grocery_store,
            amount=Decimal("500.00"),
            is_ai_suggested=True,
        )

        self.allocation2 = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan,
            payoree=self.utility_company,
            amount=Decimal("150.00"),
            is_ai_suggested=False,
        )

    def test_allocation_delete_confirm_view(self):
        """Test the deletion confirmation view."""
        url = reverse("budgets:allocation_delete_confirm", args=[self.allocation1.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        # Parse JSON response
        data = response.json()

        self.assertEqual(data["allocation_id"], self.allocation1.id)
        self.assertTrue(data["confirmation_required"])
        self.assertIn("confirmation_data", data)

        # Check confirmation data structure
        confirmation_data = data["confirmation_data"]
        self.assertIn("allocation", confirmation_data)
        self.assertIn("impact_summary", confirmation_data)

        # Check allocation data
        allocation_data = confirmation_data["allocation"]
        self.assertEqual(allocation_data["payoree_name"], "Test Grocery Store")
        self.assertEqual(float(allocation_data["amount"]), 500.00)

    def test_allocation_delete_view_success(self):
        """Test successful allocation deletion via POST."""
        url = reverse("budgets:allocation_delete", args=[self.allocation1.id])

        initial_count = BudgetAllocation.objects.count()

        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)

        # Parse JSON response
        data = response.json()

        self.assertTrue(data["success"])
        self.assertEqual(
            data["deleted_allocation"]["payoree_name"], "Test Grocery Store"
        )
        self.assertIn("redirect_url", data)

        # Verify deletion
        self.assertEqual(BudgetAllocation.objects.count(), initial_count - 1)
        self.assertFalse(
            BudgetAllocation.objects.filter(id=self.allocation1.id).exists()
        )

    def test_allocation_delete_view_nonexistent(self):
        """Test deletion of non-existent allocation."""
        url = reverse("budgets:allocation_delete", args=[99999])

        response = self.client.post(url)

        self.assertEqual(response.status_code, 404)

    def test_allocation_delete_view_inactive_budget(self):
        """Test deletion from inactive budget plan."""
        # Make budget inactive
        self.budget_plan.is_active = False
        self.budget_plan.save()

        url = reverse("budgets:allocation_delete", args=[self.allocation1.id])

        response = self.client.post(url)

        self.assertEqual(response.status_code, 400)

        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("inactive budget", data["error"])

    def test_bulk_allocation_delete_view_success(self):
        """Test successful bulk allocation deletion."""
        url = reverse("budgets:allocation_bulk_delete")

        initial_count = BudgetAllocation.objects.count()

        # Prepare bulk delete data
        delete_data = {
            "allocation_ids": [self.allocation1.id, self.allocation2.id],
            "force": False,
        }

        response = self.client.post(
            url, data=json.dumps(delete_data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Parse JSON response
        data = response.json()

        self.assertTrue(data["success"])
        self.assertEqual(data["deleted_count"], 2)
        self.assertEqual(float(data["total_amount"]), 650.00)  # 500 + 150

        # Verify deletions
        self.assertEqual(BudgetAllocation.objects.count(), initial_count - 2)

    def test_bulk_allocation_delete_view_empty_list(self):
        """Test bulk deletion with empty allocation list."""
        url = reverse("budgets:allocation_bulk_delete")

        delete_data = {"allocation_ids": [], "force": False}

        response = self.client.post(
            url, data=json.dumps(delete_data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("No allocations selected", data["error"])

    def test_bulk_allocation_delete_view_nonexistent_ids(self):
        """Test bulk deletion with some non-existent IDs."""
        url = reverse("budgets:allocation_bulk_delete")

        delete_data = {"allocation_ids": [self.allocation1.id, 99999], "force": False}

        response = self.client.post(
            url, data=json.dumps(delete_data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("could not be found", data["error"])

    def test_allocation_impact_analysis_view(self):
        """Test the impact analysis view."""
        # Add some transactions for impact analysis
        Transaction.objects.create(
            source="test.csv",
            sheet_account="checking",
            account_type="checking",
            date=date(2025, 10, 15),
            amount=Decimal("-75.00"),
            description="Test transaction",
            payoree=self.grocery_store,
            category=self.groceries_category,
        )

        url = reverse("budgets:allocation_impact_analysis", args=[self.allocation1.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        # Parse JSON response
        data = response.json()

        self.assertEqual(data["allocation_id"], self.allocation1.id)
        self.assertIn("impact_analysis", data)

        # Check impact analysis structure
        impact = data["impact_analysis"]
        self.assertIn("allocation_amount", impact)
        self.assertIn("payoree_name", impact)
        self.assertIn("transactions", impact)
        self.assertIn("spending", impact)
        self.assertIn("budget_impact", impact)

    def test_allocation_impact_analysis_view_nonexistent(self):
        """Test impact analysis for non-existent allocation."""
        url = reverse("budgets:allocation_impact_analysis", args=[99999])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)
