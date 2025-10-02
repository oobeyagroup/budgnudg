"""
ATDD Tests for Budget Admin Management

Tests the Django Admin interface functionality for Budget Plans and Budget Allocations.
Covers admin list views, forms, filtering, searching, inline management, and permissions.
"""

import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.admin.sites import AdminSite
from django.contrib import admin
from django.http import HttpRequest

from budgets.models import BudgetPlan, BudgetAllocation
from budgets.admin import BudgetPlanAdmin, BudgetAllocationAdmin
from transactions.models import Payoree, Category
from atdd_tracker import user_story, acceptance_test


@user_story("budgets", "admin_budget_management")
class TestBudgetAdminManagementATDD(TestCase):
    """ATDD tests for budget admin management functionality."""

    def setUp(self):
        """Set up test data."""
        # Create admin user
        self.admin_user = User.objects.create_superuser(
            username="admin", email="admin@test.com", password="adminpass123"
        )

        # Create regular user
        self.regular_user = User.objects.create_user(
            username="user", email="user@test.com", password="userpass123"
        )

        # Create test category and payoree
        self.category = Category.objects.create(name="Test Category", type="expense")

        self.payoree = Payoree.objects.create(
            name="Test Payoree", default_category=self.category
        )

        # Create test budget plan
        self.budget_plan = BudgetPlan.objects.create(
            name="Test Plan",
            year=2025,
            month=10,
            is_active=True,
            description="Test budget plan",
        )

        # Create test budget allocation
        self.budget_allocation = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan,
            payoree=self.payoree,
            amount=Decimal("100.00"),
            baseline_amount=Decimal("95.00"),
            is_ai_suggested=True,
            user_note="Test allocation",
        )

        self.client = Client()

        # Admin site setup
        self.admin_site = AdminSite()
        self.budget_plan_admin = BudgetPlanAdmin(BudgetPlan, self.admin_site)
        self.budget_allocation_admin = BudgetAllocationAdmin(
            BudgetAllocation, self.admin_site
        )

    @acceptance_test(
        name="Budget Plan Admin Access",
        criteria_id="budget_plan_admin_access",
        given="I am logged in as an admin user",
        when="I navigate to the Django Admin interface",
        then="I should see Budget Plans in the admin menu and can manage them",
    )
    def test_budget_plan_admin_access(self):
        """Test that admin users can access budget plan admin."""
        # Login as admin
        self.client.login(username="admin", password="adminpass123")

        # Access admin index
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)

        # Check Budget Plans are listed
        self.assertContains(response, "Budget plans")

        # Access budget plan list view
        response = self.client.get("/admin/budgets/budgetplan/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Plan")

        # Access budget plan add form
        response = self.client.get("/admin/budgets/budgetplan/add/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Name:")
        self.assertContains(response, "Year:")

        # Access budget plan edit form
        response = self.client.get(
            f"/admin/budgets/budgetplan/{self.budget_plan.id}/change/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Plan")

    @acceptance_test(
        name="Budget Plan List View",
        criteria_id="budget_plan_list_view",
        given="I am viewing the Budget Plans admin list",
        when="I look at the list display",
        then="I should see appropriate columns and can filter/search",
    )
    def test_budget_plan_list_view(self):
        """Test budget plan admin list view functionality."""
        self.client.login(username="admin", password="adminpass123")

        # Test list display
        response = self.client.get("/admin/budgets/budgetplan/")
        self.assertEqual(response.status_code, 200)

        # Check list display columns
        self.assertContains(response, "Name")
        self.assertContains(response, "Period")
        self.assertContains(response, "Is active")
        self.assertContains(response, "Allocations")
        self.assertContains(response, "Total Allocated")
        self.assertContains(response, "Test Plan")
        self.assertContains(response, "October 2025")  # Period display

        # Test filtering by year
        response = self.client.get("/admin/budgets/budgetplan/?year__exact=2025")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Plan")

        # Test filtering by active status
        response = self.client.get("/admin/budgets/budgetplan/?is_active__exact=1")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Plan")

        # Test search by name
        response = self.client.get("/admin/budgets/budgetplan/?q=Test")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Plan")

    @acceptance_test(
        name="Budget Plan Form Management",
        criteria_id="budget_plan_form_management",
        given="I am creating or editing a budget plan",
        when="I fill out the form",
        then="I should see all fields with validation and descriptions",
    )
    def test_budget_plan_form_management(self):
        """Test budget plan form functionality and validation."""
        self.client.login(username="admin", password="adminpass123")

        # Test form fields are present
        response = self.client.get("/admin/budgets/budgetplan/add/")
        self.assertEqual(response.status_code, 200)

        # Check all expected fields
        self.assertContains(response, 'name="name"')
        self.assertContains(response, 'name="year"')
        self.assertContains(response, 'name="month"')
        self.assertContains(response, 'name="is_active"')
        self.assertContains(response, 'name="description"')

        # Test successful form submission (including inline formset data)
        response = self.client.post(
            "/admin/budgets/budgetplan/add/",
            {
                "name": "New Plan",
                "year": 2025,
                "month": 11,
                "is_active": True,
                "description": "New test plan",
                # Inline formset data
                "allocations-TOTAL_FORMS": "1",
                "allocations-INITIAL_FORMS": "0",
                "allocations-MIN_NUM_FORMS": "0",
                "allocations-MAX_NUM_FORMS": "1000",
                "allocations-0-payoree": "",
                "allocations-0-amount": "",
                "allocations-0-baseline_amount": "",
                "allocations-0-is_ai_suggested": "",
                "allocations-0-user_note": "",
            },
        )
        self.assertEqual(response.status_code, 302)  # Redirect after success

        # Verify plan was created
        new_plan = BudgetPlan.objects.get(name="New Plan")
        self.assertEqual(new_plan.year, 2025)
        self.assertEqual(new_plan.month, 11)
        self.assertTrue(new_plan.is_active)

        # Test unique constraint validation
        response = self.client.post(
            "/admin/budgets/budgetplan/add/",
            {
                "name": "New Plan",  # Same name, year, month
                "year": 2025,
                "month": 11,
                "is_active": True,
                "description": "Duplicate plan",
            },
        )
        self.assertEqual(response.status_code, 200)  # Form redisplayed with errors
        self.assertContains(
            response, "Budget plan with this Name, Year and Month already exists"
        )

    @acceptance_test(
        name="Budget Allocation Admin Access",
        criteria_id="budget_allocation_admin_access",
        given="I am logged in as an admin user",
        when="I navigate to the Django Admin interface",
        then="I should see Budget Allocations in the admin menu and can manage them",
    )
    def test_budget_allocation_admin_access(self):
        """Test that admin users can access budget allocation admin."""
        self.client.login(username="admin", password="adminpass123")

        # Access admin index
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)

        # Check Budget Allocations are listed
        self.assertContains(response, "Budget allocations")

        # Access budget allocation list view
        response = self.client.get("/admin/budgets/budgetallocation/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Payoree")

        # Access budget allocation add form
        response = self.client.get("/admin/budgets/budgetallocation/add/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Budget plan:")
        self.assertContains(response, "Payoree:")

    @acceptance_test(
        name="Budget Allocation List View",
        criteria_id="budget_allocation_list_view",
        given="I am viewing the Budget Allocations admin list",
        when="I look at the list display",
        then="I should see appropriate columns and can filter/search",
    )
    def test_budget_allocation_list_view(self):
        """Test budget allocation admin list view functionality."""
        self.client.login(username="admin", password="adminpass123")

        # Test list display
        response = self.client.get("/admin/budgets/budgetallocation/")
        self.assertEqual(response.status_code, 200)

        # Check list display columns
        self.assertContains(response, "Budget plan")
        self.assertContains(response, "Payoree")
        self.assertContains(response, "Amount")
        self.assertContains(response, "AI suggested")
        self.assertContains(response, "Test Payoree")
        self.assertContains(response, "$100.00")

        # Test search by payoree name
        response = self.client.get("/admin/budgets/budgetallocation/?q=Test")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Payoree")

        # Test filtering by AI suggested
        response = self.client.get(
            "/admin/budgets/budgetallocation/?is_ai_suggested__exact=1"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Payoree")

    @acceptance_test(
        name="Budget Allocation Form Management",
        criteria_id="budget_allocation_form_management",
        given="I am creating or editing a budget allocation",
        when="I fill out the form",
        then="I should see all fields with validation and effective category",
    )
    def test_budget_allocation_form_management(self):
        """Test budget allocation form functionality and validation."""
        self.client.login(username="admin", password="adminpass123")

        # Test form fields are present
        response = self.client.get("/admin/budgets/budgetallocation/add/")
        self.assertEqual(response.status_code, 200)

        # Check all expected fields
        self.assertContains(response, 'name="budget_plan"')
        self.assertContains(response, 'name="payoree"')
        self.assertContains(response, 'name="amount"')
        self.assertContains(response, 'name="baseline_amount"')
        self.assertContains(response, 'name="is_ai_suggested"')
        self.assertContains(response, 'name="user_note"')

        # Create another payoree for testing
        another_payoree = Payoree.objects.create(
            name="Another Payoree", default_category=self.category
        )

        # Test successful form submission
        response = self.client.post(
            "/admin/budgets/budgetallocation/add/",
            {
                "budget_plan": self.budget_plan.id,
                "payoree": another_payoree.id,
                "amount": "150.00",
                "baseline_amount": "140.00",
                "is_ai_suggested": False,
                "user_note": "Manual allocation",
            },
        )
        self.assertEqual(response.status_code, 302)  # Redirect after success

        # Verify allocation was created
        new_allocation = BudgetAllocation.objects.get(payoree=another_payoree)
        self.assertEqual(new_allocation.amount, Decimal("150.00"))
        self.assertFalse(new_allocation.is_ai_suggested)

        # Test unique constraint validation
        response = self.client.post(
            "/admin/budgets/budgetallocation/add/",
            {
                "budget_plan": self.budget_plan.id,
                "payoree": another_payoree.id,  # Same budget plan and payoree
                "amount": "200.00",
                "baseline_amount": "180.00",
                "is_ai_suggested": True,
                "user_note": "Duplicate allocation",
            },
        )
        self.assertEqual(response.status_code, 200)  # Form redisplayed with errors
        self.assertContains(
            response,
            "Budget allocation with this Budget plan and Payoree already exists",
        )

    @acceptance_test(
        name="Inline Allocation Management",
        criteria_id="inline_allocation_management",
        given="I am editing a budget plan",
        when="I view the budget plan form",
        then="I should see inline allocations and can manage them",
    )
    def test_inline_allocation_management(self):
        """Test inline allocation management in budget plan admin."""
        self.client.login(username="admin", password="adminpass123")

        # Access budget plan edit form
        response = self.client.get(
            f"/admin/budgets/budgetplan/{self.budget_plan.id}/change/"
        )
        self.assertEqual(response.status_code, 200)

        # Check that inline allocation section exists
        self.assertContains(response, "Budget allocations")
        self.assertContains(response, "Test Payoree")
        self.assertContains(response, "100.00")

        # Check for inline form fields
        self.assertContains(response, "allocations-0-payoree")
        self.assertContains(response, "allocations-0-amount")

    @acceptance_test(
        name="Admin Permissions and Security",
        criteria_id="admin_permissions_security",
        given="I am a non-admin user",
        when="I try to access budget admin pages",
        then="I should be redirected to login and need admin permissions",
    )
    def test_admin_permissions_security(self):
        """Test admin security and permissions."""
        # Test unauthenticated access
        response = self.client.get("/admin/budgets/budgetplan/")
        self.assertEqual(response.status_code, 302)  # Redirect to login
        self.assertIn("/admin/login/", response.url)

        # Test regular user access
        self.client.login(username="user", password="userpass123")
        response = self.client.get("/admin/budgets/budgetplan/")
        self.assertEqual(response.status_code, 302)  # Redirect to login

        # Test admin user access works
        self.client.login(username="admin", password="adminpass123")
        response = self.client.get("/admin/budgets/budgetplan/")
        self.assertEqual(response.status_code, 200)  # Success

    @acceptance_test(
        name="Data Validation and Error Handling",
        criteria_id="data_validation_error_handling",
        given="I am creating or editing budget data",
        when="I submit invalid data",
        then="I should see clear validation error messages",
    )
    def test_data_validation_error_handling(self):
        """Test form validation and error handling."""
        self.client.login(username="admin", password="adminpass123")

        # Test invalid year (negative)
        response = self.client.post(
            "/admin/budgets/budgetplan/add/",
            {
                "name": "Invalid Plan",
                "year": -1,  # Invalid negative year
                "month": 1,
                "is_active": True,
            },
        )
        self.assertEqual(response.status_code, 200)  # Form redisplayed with errors

        # Test invalid month (too high)
        response = self.client.post(
            "/admin/budgets/budgetplan/add/",
            {
                "name": "Invalid Plan",
                "year": 2025,
                "month": 15,  # Invalid month
                "is_active": True,
            },
        )
        self.assertEqual(response.status_code, 200)  # Form redisplayed with errors

        # Test missing required fields
        response = self.client.post(
            "/admin/budgets/budgetallocation/add/",
            {
                "budget_plan": "",  # Missing required field
                "payoree": self.payoree.id,
                "amount": "100.00",
            },
        )
        self.assertEqual(response.status_code, 200)  # Form redisplayed with errors
        self.assertContains(response, "This field is required")

    @acceptance_test(
        name="Admin List Display Configuration",
        criteria_id="admin_list_display_configuration",
        given="I am viewing admin list pages",
        when="I look at the configuration",
        then="The list displays should show appropriate fields and formatting",
    )
    def test_admin_list_display_configuration(self):
        """Test admin list display configuration."""
        # Test BudgetPlanAdmin configuration
        expected_list_display = [
            "name",
            "period_display",
            "is_active",
            "allocation_count",
            "total_amount",
            "created_at",
        ]
        self.assertEqual(self.budget_plan_admin.list_display, expected_list_display)

        expected_list_filter = ["year", "month", "is_active"]
        self.assertEqual(self.budget_plan_admin.list_filter, expected_list_filter)

        expected_search_fields = ["name"]
        self.assertEqual(self.budget_plan_admin.search_fields, expected_search_fields)

        # Test BudgetAllocationAdmin configuration
        expected_allocation_display = [
            "budget_plan",
            "payoree",
            "effective_category_display",
            "amount",
            "baseline_amount",
            "variance_display",
            "is_ai_suggested",
            "recurring_series",
        ]
        self.assertEqual(
            self.budget_allocation_admin.list_display, expected_allocation_display
        )

        expected_allocation_filter = [
            "budget_plan__year",
            "budget_plan__month",
            "is_ai_suggested",
            "payoree__default_category",
            ("recurring_series", admin.RelatedOnlyFieldListFilter),
        ]
        self.assertEqual(
            self.budget_allocation_admin.list_filter, expected_allocation_filter
        )

        expected_allocation_search = [
            "budget_plan__name",
            "payoree__name",
            "payoree__default_category__name",
            "user_note",
        ]
        self.assertEqual(
            self.budget_allocation_admin.search_fields, expected_allocation_search
        )
