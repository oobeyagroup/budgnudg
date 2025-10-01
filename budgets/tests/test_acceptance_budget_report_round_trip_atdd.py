"""
ATDD Tests for Budget Report Classification Round Trip Navigation

These tests follow the acceptance criteria defined in:
docs/user_stories/budgets/budger_report_classification_round_trip_atdd.md

This file implements incremental ATDD for seamless navigation between
Budget Report and Budget by Classification Analysis views.
"""

from django.test import TestCase, Client
from django.urls import reverse
from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta

from budgets.models import BudgetPlan, BudgetAllocation
from transactions.models import Category, Payoree, Transaction


class TestBudgetReportRoundTripATDD(TestCase):
    """ATDD tests for Budget Report Classification Round Trip Navigation."""

    def setUp(self):
        """Set up test data for round trip navigation testing."""
        self.client = Client()

        # Create test categories with hierarchy
        self.groceries_category = Category.objects.create(
            name="Groceries", type="expense"
        )
        self.food_subcategory = Category.objects.create(
            name="Food", type="expense", parent=self.groceries_category
        )
        self.dining_subcategory = Category.objects.create(
            name="Dining Out", type="expense", parent=self.groceries_category
        )
        self.utilities_category = Category.objects.create(
            name="Utilities", type="expense"
        )

        # Create test payorees with default subcategories for drill-down testing
        self.grocery_store = Payoree.objects.create(
            name="Whole Foods", 
            default_category=self.groceries_category,
            default_subcategory=self.food_subcategory
        )
        self.restaurant = Payoree.objects.create(
            name="Local Restaurant", 
            default_category=self.groceries_category,
            default_subcategory=self.dining_subcategory
        )

        # Create current and future budget plans
        today = date.today()
        current_month = today.replace(day=1)

        self.current_budget_plan = BudgetPlan.objects.create(
            name="Current Budget",
            year=current_month.year,
            month=current_month.month,
            is_active=True,
        )

        next_month = current_month + relativedelta(months=1)
        self.next_budget_plan = BudgetPlan.objects.create(
            name="Next Month Budget",
            year=next_month.year,
            month=next_month.month,
            is_active=False,
        )

        # Create budget allocations using payoree-centric model
        # Grocery store allocation (groceries category via payoree default)
        self.groceries_allocation = BudgetAllocation.objects.create(
            budget_plan=self.current_budget_plan,
            payoree=self.grocery_store,
            amount=Decimal("800.00"),
        )

        # Restaurant allocation (also groceries category via payoree default)
        self.restaurant_allocation = BudgetAllocation.objects.create(
            budget_plan=self.current_budget_plan,
            payoree=self.restaurant,
            amount=Decimal("200.00"),
        )

        # Next month allocation for testing future budget navigation
        self.next_month_groceries = BudgetAllocation.objects.create(
            budget_plan=self.next_budget_plan,
            payoree=self.grocery_store,
            amount=Decimal("850.00"),
        )

        # Create some historical transactions for context
        Transaction.objects.create(
            source="test_file.csv",
            sheet_account="expense",
            account_type="checking",
            date=date(2025, 9, 15),  # Use date instead of datetime
            amount=Decimal("-125.50"),
            description="Grocery shopping",
            payoree=self.grocery_store,
            category=self.groceries_category,
        )

    def test_budget_report_category_drill_down(self):
        """
        ATDD Test: budget_report_category_drill_down

        Given I'm viewing the Budget Report,
        when I click on a category row,
        then I'm taken to the Budget by Classification Analysis for that category.
        """
        # Given: I'm viewing the Budget Report
        budget_report_url = reverse("budgets:report")
        response = self.client.get(budget_report_url)

        # Verify Budget Report loads successfully
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Groceries")
        # The Budget Report shows payoree allocations grouped by category
        self.assertContains(
            response, "1,000.00"
        )  # Total from grocery store + restaurant allocations

        # When: I click on a category row (simulated by constructing the expected drill-down URL)
        # The drill-down link should be generated in the Budget Report template
        expected_drill_down_url = reverse("budgets:classification_analysis") + (
            f"?classification_type=category&category_id={self.groceries_category.pk}"
            f"&return=budget_report"
        )

        # First, verify the Budget Report template contains the drill-down link
        # This will fail initially and drive template enhancement
        self.assertContains(
            response,
            f'href="{expected_drill_down_url}"',
            msg_prefix="Budget Report should contain drill-down link to Classification Analysis",
        )

        # Then: I'm taken to the Budget by Classification Analysis for that category
        classification_response = self.client.get(expected_drill_down_url)

        self.assertEqual(classification_response.status_code, 200)
        self.assertContains(classification_response, "Analyzing: Groceries")
        self.assertContains(classification_response, "Type: Category")

        # Verify the return parameter is preserved for return navigation
        self.assertContains(
            classification_response,
            'value="budget_report"',
            msg_prefix="Classification Analysis should preserve return context in hidden form field",
        )

    def test_budget_report_subcategory_drill_down(self):
        """
        ATDD Test: budget_report_subcategory_drill_down

        Given I'm viewing the Budget Report,
        when I click on a subcategory row,
        then I'm taken to the Budget by Classification Analysis for that subcategory.
        """
        # Given: I'm viewing the Budget Report
        budget_report_url = reverse("budgets:report")
        response = self.client.get(budget_report_url)

        self.assertEqual(response.status_code, 200)

        # When: I click on a subcategory row
        expected_drill_down_url = reverse("budgets:classification_analysis") + (
            f"?classification_type=subcategory"
            f"&category_id={self.groceries_category.pk}"
            f"&subcategory_id={self.food_subcategory.pk}"
            f"&return=budget_report"
        )

        # Verify the Budget Report template contains the subcategory drill-down link
        self.assertContains(
            response,
            f'href="{expected_drill_down_url}"',
            msg_prefix="Budget Report should contain subcategory drill-down link",
        )

        # Then: I'm taken to the Budget by Classification Analysis for that subcategory
        classification_response = self.client.get(expected_drill_down_url)

        self.assertEqual(classification_response.status_code, 200)
        self.assertContains(classification_response, "Analyzing: Food")
        self.assertContains(classification_response, "Type: Subcategory")

    def test_budget_report_payoree_drill_down(self):
        """
        ATDD Test: budget_report_payoree_drill_down

        Given I'm viewing the Budget Report with payoree-level allocations,
        when I click on a payoree allocation,
        then I'm taken to the Budget by Classification Analysis for that payoree.
        """
        # Given: I'm viewing the Budget Report with payoree allocations
        budget_report_url = reverse("budgets:report")
        response = self.client.get(budget_report_url)

        self.assertEqual(response.status_code, 200)
        # Verify payoree allocation appears in report
        self.assertContains(response, "Local Restaurant")

        # When: I click on a payoree allocation
        expected_drill_down_url = reverse("budgets:classification_analysis") + (
            f"?classification_type=payoree"
            f"&payoree_id={self.restaurant.pk}"
            f"&return=budget_report"
        )

        # This test will initially fail and drive payoree drill-down implementation
        self.assertContains(
            response,
            f'href="{expected_drill_down_url}"',
            msg_prefix="Budget Report should contain payoree drill-down link",
        )

        # Then: I'm taken to the Budget by Classification Analysis for that payoree
        classification_response = self.client.get(expected_drill_down_url)

        self.assertEqual(classification_response.status_code, 200)
        self.assertContains(classification_response, "Analyzing: Local Restaurant")
        self.assertContains(classification_response, "Type: Payoree")

    def test_drill_down_context_preservation(self):
        """
        ATDD Test: drill_down_context_preservation

        Given I drill down from Budget Report to Classification Analysis,
        when the Classification Analysis page loads,
        then it displays the correct classification type and selection that matches what I clicked.
        """
        # Given: I drill down from Budget Report to Classification Analysis for Groceries category
        drill_down_url = reverse("budgets:classification_analysis") + (
            f"?classification_type=category&category_id={self.groceries_category.pk}"
            f"&return=budget_report"
        )

        # When: The Classification Analysis page loads
        response = self.client.get(drill_down_url)

        # Then: It displays the correct classification type and selection
        self.assertEqual(response.status_code, 200)

        # Verify correct classification type is selected
        self.assertContains(response, 'value="category"')

        # Verify correct category is selected
        self.assertContains(response, f'value="{self.groceries_category.pk}"')
        self.assertContains(response, "Analyzing: Groceries")

        # Verify the analysis shows the category data
        self.assertContains(response, "Type: Category")

        # Verify return context is preserved
        self.assertIn("return_to", response.context or {})

    def test_classification_return_to_report(self):
        """
        ATDD Test: classification_return_to_report

        Given I'm viewing Budget by Classification Analysis,
        when I click a "Back to Budget Report" link,
        then I return to the Budget Report.
        """
        # Given: I'm viewing Budget by Classification Analysis with return context
        classification_url = reverse("budgets:classification_analysis") + (
            f"?classification_type=category&category_id={self.groceries_category.pk}"
            f"&return=budget_report"
        )

        response = self.client.get(classification_url)
        self.assertEqual(response.status_code, 200)

        # When: I click a "Back to Budget Report" link
        # The template should contain a return link when return parameter is present
        expected_return_url = reverse("budgets:report")

        # This will initially fail and drive return navigation implementation
        self.assertContains(
            response,
            f'href="{expected_return_url}"',
            msg_prefix="Classification Analysis should contain return link when return context exists",
        )

        self.assertContains(
            response,
            "Back to Budget Report",
            msg_prefix="Return link should have descriptive text",
        )

        # Then: I return to the Budget Report
        return_response = self.client.get(expected_return_url)
        self.assertEqual(return_response.status_code, 200)
        self.assertContains(return_response, "Budget Report")

    def tearDown(self):
        """Clean up test data."""
        # Clean up in reverse order of dependencies
        Transaction.objects.all().delete()
        BudgetAllocation.objects.all().delete()
        BudgetPlan.objects.all().delete()
        Payoree.objects.all().delete()
        Category.objects.all().delete()
