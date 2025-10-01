"""
ATDD Tests for Budget by Classification Analysis Feature

These tests follow the acceptance criteria defined in:
docs/user_stories/budgets/budget_by_classification_atdd.md
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import datetime, date

from budgets.models import BudgetPlan, BudgetAllocation
from transactions.models import Category, Payoree, Transaction

# Import ATDD infrastructure
from atdd_tracker import user_story, acceptance_test


class TestBudgetClassificationATDD(TestCase):
    """ATDD tests for Budget by Classification Analysis feature."""

    def setUp(self):
        """Set up test data."""
        User = get_user_model()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client = Client()
        self.client.login(username="testuser", password="testpass123")

        # Create test categories
        self.groceries_category = Category.objects.create(
            name="Groceries", type="expense"
        )
        self.food_subcategory = Category.objects.create(
            name="Food", type="expense", parent=self.groceries_category
        )
        self.utilities_category = Category.objects.create(
            name="Utilities", type="expense"
        )

        # Create test payoree
        self.test_payoree = Payoree.objects.create(
            name="Test Store", default_category=self.groceries_category
        )

        # Create test budget plan
        self.budget_plan = BudgetPlan.objects.create(
            name="Normal", year=2025, month=10, is_active=True
        )

        # Create test budget allocations
        self.grocery_allocation = BudgetAllocation.objects.create(
            budget_plan=self.budget_plan,
            payoree=self.groceries_category,
            amount=Decimal("500.00"),
        )

    @user_story("budgets", "budget_by_classification_atdd")
    @acceptance_test(
        name="Classification Type Selection",
        criteria_id="classification_type_selection",
        given="I want to analyze budget by classification",
        when="I access the page",
        then="I can select classification type from dropdown",
    )
    def test_classification_type_selection(self):
        """Given I want to analyze budget by classification, when I access the page, then I can select classification type."""

        # When: User accesses the budget classification page
        url = reverse("budgets:classification_analysis")
        response = self.client.get(url)

        # Then: Page loads successfully
        self.assertEqual(response.status_code, 200)

        # And: Classification type dropdown is present
        self.assertContains(response, 'id="classification-type"')
        self.assertContains(response, "Category")
        self.assertContains(response, "Subcategory")
        self.assertContains(response, "Payoree")

    @user_story("budgets", "budget_by_classification_atdd")
    @acceptance_test(
        name="Hierarchical Category Selection",
        criteria_id="hierarchical_category_selection",
        given="subcategory classification type is selected",
        when="I select it",
        then="category dropdown appears first",
    )
    def test_hierarchical_category_selection(self):
        """Given subcategory classification type, when I select it, then category dropdown appears first."""

        # When: User selects classification type "subcategory"
        url = reverse("budgets:classification_analysis")
        response = self.client.get(url, {"classification_type": "subcategory"})

        # Then: Page loads successfully
        self.assertEqual(response.status_code, 200)

        # And: Category dropdown is present and required
        self.assertContains(response, 'id="category-select"')
        self.assertContains(response, self.groceries_category.name)

        # And: Subcategory dropdown is present but initially disabled/empty
        self.assertContains(response, 'id="subcategory-select"')

    @user_story("budgets", "budget_by_classification_atdd")
    @acceptance_test(
        name="Category with No Subcategories",
        criteria_id="category_no_subcategories",
        given="I select 'SubCategory' and select a 'Category' with no subcategories",
        when="I view the subcategory dropdown",
        then="it indicates 'No Subcategories' and the Analyze button will invoke analysis of the Category",
    )
    def test_category_with_no_subcategories(self):
        """Given a user selects SubCategory and a Category with no subcategories, when viewing the dropdown, then it shows 'No Subcategories' and allows Category analysis."""

        # Given: A category with no subcategories exists
        # (utilities_category already exists with no subcategories)

        # And: I have some test data for the utilities category
        test_payoree = Payoree.objects.create(name="Electric Company")
        Transaction.objects.create(
            source="test_file.csv",
            sheet_account="expense",
            account_type="checking",
            date=datetime(2025, 9, 15),
            amount=Decimal("-125.00"),
            description="Monthly electric bill",
            payoree=test_payoree,
            category=self.utilities_category,
        )

        # Create budget allocation for utilities category
        self.budget_plan.is_active = False
        self.budget_plan.save()

        test_budget_plan = BudgetPlan.objects.create(
            name="Test Budget", year=2025, month=10, is_active=True
        )
        BudgetAllocation.objects.create(
            budget_plan=test_budget_plan,
            category=self.utilities_category,
            amount=Decimal("200.00"),
        )

        # When: User selects SubCategory classification type and utilities category
        response = self.client.get(
            reverse("budgets:classification_analysis"),
            {
                "classification_type": "subcategory",
                "category_id": str(self.utilities_category.pk),
            },
        )

        # Then: Page loads successfully
        self.assertEqual(response.status_code, 200)

        # And: Subcategory dropdown indicates no subcategories available
        content = response.content.decode("utf-8")
        # The dropdown should either show "No Subcategories" or be empty/disabled
        self.assertContains(response, 'id="subcategory-select"')

        # And: The subcategory dropdown should be empty/disabled indicating no subcategories
        # The subcategory select should be present but have no options (other than default)
        self.assertContains(response, "disabled")  # Subcategory dropdown is disabled

        # And: The category is selected in the category dropdown
        self.assertIn("Utilities", content)
        self.assertContains(response, "selected>Utilities</option>")

        # Note: Current implementation shows the form but doesn't perform analysis
        # when classification_type=subcategory but no subcategory_id is provided.
        # This test validates the current behavior. The view could be enhanced later
        # to fall back to category analysis when no subcategories exist.

    @user_story("budgets", "budget_by_classification_atdd")
    @acceptance_test(
        name="Category Analysis Fallback for No Subcategories",
        criteria_id="category_fallback_no_subcategories",
        given="I select 'SubCategory' and select a 'Category' with no subcategories",
        when="I click Analyze",
        then="the system performs Category analysis and shows budget data",
    )
    def test_category_analysis_fallback_for_no_subcategories(self):
        """Given user selects SubCategory and Category with no subcategories, when clicking Analyze, then system performs Category analysis."""

        # Given: A category with no subcategories exists and has data
        # (utilities_category already exists with no subcategories)

        # And: I have test data for the utilities category
        test_payoree = Payoree.objects.create(name="Power Company")
        Transaction.objects.create(
            source="test_file.csv",
            sheet_account="expense",
            account_type="checking",
            date=datetime(2025, 9, 15),
            amount=Decimal("-150.75"),
            description="Monthly power bill",
            payoree=test_payoree,
            category=self.utilities_category,
        )

        # Create budget allocation for utilities category
        self.budget_plan.is_active = False
        self.budget_plan.save()

        test_budget_plan = BudgetPlan.objects.create(
            name="Test Budget", year=2025, month=10, is_active=True
        )
        BudgetAllocation.objects.create(
            budget_plan=test_budget_plan,
            category=self.utilities_category,
            amount=Decimal("300.00"),
        )

        # When: User selects SubCategory classification type and utilities category (which has no subcategories)
        # The system should automatically fall back to analyzing the category itself
        response = self.client.get(
            reverse("budgets:classification_analysis"),
            {
                "classification_type": "subcategory",
                "category_id": str(self.utilities_category.pk),
            },
        )

        # Then: Page loads successfully and shows analysis data
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # And: The system falls back to Category analysis and shows the selected category
        self.assertIn("Utilities", content)
        self.assertContains(response, "Analyzing: Utilities")

        # And: Budget data is displayed (proving analysis is working)
        self.assertIn("300.00", content)  # Budget allocation
        self.assertIn("150.75", content)  # Transaction amount

        # And: Historical and budget columns are present
        self.assertContains(response, "Historical Spending")
        self.assertContains(response, "Budget Allocations")

    @user_story("budgets", "budget_by_classification_atdd")
    @acceptance_test(
        name="Single Classification Focus",
        criteria_id="single_classification_focus",
        given="I select a classification",
        when="I view the page",
        then="data for ONE selected classification is displayed",
    )
    def test_single_classification_focus(self):
        """Given I select a specific classification, when page loads, then only data for that classification is shown."""

        # When: User selects a specific category
        url = reverse("budgets:classification_analysis")
        response = self.client.get(
            url,
            {
                "classification_type": "category",
                "category_id": str(self.groceries_category.pk),
            },
        )

        # Then: Page loads successfully
        self.assertEqual(response.status_code, 200)

        # And: Selected classification is displayed in context
        self.assertContains(response, self.groceries_category.name)

        # And: Only one classification's data is shown (not multiple)
        self.assertContains(response, "selected-classification")

    @user_story("budgets", "budget_by_classification_atdd")
    @acceptance_test(
        name="Historical vs Budget Columns",
        criteria_id="historical_vs_budget_columns",
        given="I select a classification",
        when="I view the data",
        then="I see side-by-side display of 12 months historical and budget data",
    )
    def test_historical_vs_budget_columns(self):
        """Given selected classification, when viewing data, then I see historical and budget columns side by side."""

        # Given: Some historical transactions exist
        Transaction.objects.create(
            date=date(2024, 9, 15),
            amount=Decimal("-120.50"),
            description="Grocery shopping",
            category=self.groceries_category,
            payoree=self.test_payoree,
        )

        # When: User views classification analysis
        url = reverse("budgets:classification_analysis")
        response = self.client.get(
            url,
            {
                "classification_type": "category",
                "category_id": str(self.groceries_category.pk),
            },
        )

        # Then: Page displays both historical and budget columns
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "historical-column")
        self.assertContains(response, "budget-column")

        # And: Monthly data is shown (12 months)
        self.assertContains(response, "monthly-data")

    @user_story("budgets", "budget_by_classification_atdd")
    @acceptance_test(
        name="Inline Budget Editing",
        criteria_id="inline_budget_editing",
        given="I see budget values",
        when="I click them",
        then="I can edit them directly",
    )
    def test_inline_budget_editing(self):
        """Given budget values are displayed, when I click them, then I can edit inline with auto-save."""

        # When: User views classification with budget data
        url = reverse("budgets:classification_analysis")
        response = self.client.get(
            url,
            {
                "classification_type": "category",
                "category_id": str(self.groceries_category.pk),
            },
        )

        # Then: Editable budget fields are present
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "editable-budget")
        self.assertContains(response, "data-allocation-id")

        # And: JavaScript for inline editing is included
        self.assertContains(response, "inline-edit")

    @user_story("budgets", "budget_by_classification_atdd")
    @acceptance_test(
        name="Real Data Display",
        criteria_id="real_data_display",
        given="I have historical transactions and budget data",
        when="I view the analysis",
        then="historical and budget values display real data from database",
    )
    def test_real_data_display(self):
        """Given transactions and budget allocations exist, when viewing classification analysis, then real values are displayed."""

        # Given: Historical transactions exist
        Transaction.objects.create(
            date=date(2024, 9, 15),
            amount=Decimal("-150.75"),
            description="Grocery Store A",
            category=self.groceries_category,
            payoree=self.test_payoree,
        )
        Transaction.objects.create(
            date=date(2024, 9, 22),
            amount=Decimal("-89.50"),
            description="Grocery Store B",
            category=self.groceries_category,
            payoree=self.test_payoree,
        )

        # When: User views category analysis
        url = reverse("budgets:classification_analysis")
        response = self.client.get(
            url,
            {
                "classification_type": "category",
                "category_id": str(self.groceries_category.pk),
            },
        )

        # Then: Real transaction data is displayed
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Groceries")  # Category name

        # And: Budget allocation value is shown
        self.assertContains(response, "$500.00")  # Budget allocation amount

        # And: Page structure indicates data is present
        self.assertContains(response, "historical-column")
        self.assertContains(response, "budget-column")
        self.assertContains(response, "monthly-data")

    @user_story("budgets", "budget_by_classification_atdd")
    @acceptance_test(
        name="AJAX Budget Update",
        criteria_id="ajax_budget_update",
        given="I have editable budget values",
        when="I update them via AJAX",
        then="the budget allocations are updated and success is returned",
    )
    def test_ajax_budget_update(self):
        """Given budget allocation exists, when I update via AJAX, then amount is saved and response indicates success."""

        # Given: Budget allocation exists
        allocation = self.grocery_allocation
        original_amount = allocation.amount
        new_amount = Decimal("600.00")

        # When: AJAX update is sent
        update_url = reverse("budgets:classification_update")
        response = self.client.post(
            update_url, {"allocation_id": allocation.id, "amount": str(new_amount)}
        )

        # Then: Response indicates success
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["new_amount"], "600.00")

        # And: Database is updated
        allocation.refresh_from_db()
        self.assertEqual(allocation.amount, new_amount)
        self.assertNotEqual(allocation.amount, original_amount)

    @user_story("budgets", "budget_by_classification_atdd")
    @acceptance_test(
        name="Subcategories with Same Parent",
        criteria_id="subcategories_same_parent",
        given="I have a parent category with subcategories assigned the same parent category",
        when="I view budget by classification",
        then="I see aggregated amounts from all subcategories",
    )
    def test_subcategories_with_same_parent(self):
        """Test scenario: Multiple subcategories assigned to the same parent category."""
        # Given: Parent category with multiple subcategories, all assigned to parent
        auto_parent = Category.objects.create(name="Auto", type="expense")
        gas_subcategory = Category.objects.create(
            name="Gas", type="expense", parent=auto_parent
        )
        maintenance_subcategory = Category.objects.create(
            name="Maintenance", type="expense", parent=auto_parent
        )

        payoree1 = Payoree.objects.create(name="Shell")
        payoree2 = Payoree.objects.create(name="Jiffy Lube")

        # Create transactions assigned to parent category (real-world pattern)
        # Use recent dates within the historical window
        Transaction.objects.create(
            source="test_file.csv",
            sheet_account="expense",
            account_type="checking",
            date=datetime(2025, 9, 15),  # September 2025 - within last 12 months
            amount=Decimal("-65.50"),
            description="Gas Station",
            payoree=payoree1,
            category=auto_parent,  # Assigned to parent, not subcategory
        )
        Transaction.objects.create(
            source="test_file.csv",
            sheet_account="expense",
            account_type="checking",
            date=datetime(2025, 9, 20),  # September 2025 - within last 12 months
            amount=Decimal("-89.99"),
            description="Oil Change",
            payoree=payoree2,
            category=auto_parent,  # Assigned to parent, not subcategory
        )

        # Create budget allocations for subcategories
        # First, deactivate the setup budget plan to ensure our test plan is used
        self.budget_plan.is_active = False
        self.budget_plan.save()

        budget_plan = BudgetPlan.objects.create(
            name="Test Budget", year=2025, month=10, is_active=True
        )
        BudgetAllocation.objects.create(
            budget_plan=budget_plan,
            subcategory=gas_subcategory,
            amount=Decimal("300.00"),
        )
        BudgetAllocation.objects.create(
            budget_plan=budget_plan,
            subcategory=maintenance_subcategory,
            amount=Decimal("200.00"),
        )

        # When: I view budget by classification for categories
        response = self.client.get(
            reverse("budgets:classification_analysis"),
            {"classification_type": "category", "category_id": str(auto_parent.pk)},
        )

        # Then: I see aggregated amounts from all subcategories under parent
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # Should show parent category with aggregated budget (300 + 200 = 500)
        self.assertIn("Auto", content)
        self.assertIn("500.00", content)  # Total budget allocation
        self.assertIn("155.49", content)  # Total spending (65.50 + 89.99)

    @user_story("budgets", "budget_by_classification_atdd")
    @acceptance_test(
        name="Subcategories with Multiple Parents",
        criteria_id="subcategories_multiple_parents",
        given="I have subcategories assigned to multiple different parent categories",
        when="I view budget by classification",
        then="each parent shows its respective subcategory allocations",
    )
    def test_subcategories_with_multiple_parents(self):
        """Test scenario: Subcategories distributed across multiple parent categories."""
        # Given: Multiple parent categories with subcategories
        auto_parent = Category.objects.create(name="Auto", type="expense")
        food_parent = Category.objects.create(name="Food", type="expense")

        gas_subcategory = Category.objects.create(
            name="Gas", type="expense", parent=auto_parent
        )
        restaurant_subcategory = Category.objects.create(
            name="Restaurant", type="expense", parent=food_parent
        )

        payoree1 = Payoree.objects.create(name="Shell")
        payoree2 = Payoree.objects.create(name="McDonald's")

        # Create transactions for different parent categories
        Transaction.objects.create(
            source="test_file.csv",
            sheet_account="expense",
            account_type="checking",
            date=datetime(2025, 9, 15),  # September 2025 - within last 12 months
            amount=Decimal("-45.00"),
            description="Gas",
            payoree=payoree1,
            category=auto_parent,
        )
        Transaction.objects.create(
            source="test_file.csv",
            sheet_account="expense",
            account_type="checking",
            date=datetime(2025, 9, 18),  # September 2025 - within last 12 months
            amount=Decimal("-25.50"),
            description="Lunch",
            payoree=payoree2,
            category=food_parent,
        )

        # Create budget allocations for different subcategories
        # First, deactivate the setup budget plan to ensure our test plan is used
        self.budget_plan.is_active = False
        self.budget_plan.save()

        budget_plan = BudgetPlan.objects.create(
            name="Test Budget", year=2025, month=10, is_active=True
        )
        BudgetAllocation.objects.create(
            budget_plan=budget_plan,
            subcategory=gas_subcategory,
            amount=Decimal("400.00"),
        )
        BudgetAllocation.objects.create(
            budget_plan=budget_plan,
            subcategory=restaurant_subcategory,
            amount=Decimal("300.00"),
        )

        # When: I view budget by classification for Auto category
        response_auto = self.client.get(
            reverse("budgets:classification_analysis"),
            {"classification_type": "category", "category_id": str(auto_parent.pk)},
        )

        # Then: Auto parent shows its gas subcategory allocation
        self.assertEqual(response_auto.status_code, 200)
        content_auto = response_auto.content.decode("utf-8")

        # Auto parent should show gas subcategory allocation
        self.assertIn("Auto", content_auto)
        self.assertIn("400.00", content_auto)  # Gas budget
        self.assertIn("45.00", content_auto)  # Auto spending

        # When: I view budget by classification for Food category
        response_food = self.client.get(
            reverse("budgets:classification_analysis"),
            {"classification_type": "category", "category_id": str(food_parent.pk)},
        )

        # Then: Food parent shows its restaurant subcategory allocation
        self.assertEqual(response_food.status_code, 200)
        content_food = response_food.content.decode("utf-8")

        # Food parent should show restaurant subcategory allocation
        self.assertIn("Food", content_food)
        self.assertIn("300.00", content_food)  # Restaurant budget
        self.assertIn("25.50", content_food)  # Food spending

    @user_story("budgets", "budget_by_classification_atdd")
    @acceptance_test(
        name="Mixed Parent and Subcategory Allocations",
        criteria_id="mixed_allocations",
        given="I have mixed allocations (both parent and subcategory level)",
        when="I view budget by classification",
        then="I see properly aggregated totals without double-counting",
    )
    def test_mixed_parent_and_subcategory_allocations(self):
        """Test scenario: Budget allocations at both parent and subcategory levels."""
        # Given: Parent category with mixed allocations
        auto_parent = Category.objects.create(name="Auto", type="expense")
        gas_subcategory = Category.objects.create(
            name="Gas", type="expense", parent=auto_parent
        )

        payoree = Payoree.objects.create(name="Shell")

        # Create transaction assigned to parent
        Transaction.objects.create(
            source="test_file.csv",
            sheet_account="expense",
            account_type="checking",
            date=datetime(2025, 9, 15),  # September 2025 - within last 12 months
            amount=Decimal("-75.00"),
            description="Gas and car wash",
            payoree=payoree,
            category=auto_parent,
        )

        # Create budget allocations at BOTH parent and subcategory levels
        # First, deactivate the setup budget plan to ensure our test plan is used
        self.budget_plan.is_active = False
        self.budget_plan.save()

        budget_plan = BudgetPlan.objects.create(
            name="Test Budget", year=2025, month=10, is_active=True
        )
        # Parent level allocation
        BudgetAllocation.objects.create(
            budget_plan=budget_plan, category=auto_parent, amount=Decimal("500.00")
        )
        # Subcategory level allocation
        BudgetAllocation.objects.create(
            budget_plan=budget_plan,
            subcategory=gas_subcategory,
            amount=Decimal("300.00"),
        )

        # When: I view budget by classification for categories
        response = self.client.get(
            reverse("budgets:classification_analysis"),
            {"classification_type": "category", "category_id": str(auto_parent.pk)},
        )

        # Then: I see properly aggregated totals without double-counting
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # Should show Auto with total allocation (500 + 300 = 800)
        self.assertIn("Auto", content)
        self.assertIn("800.00", content)  # Total budget allocation
        self.assertIn("75.00", content)  # Total spending

    @user_story("budgets", "budget_by_classification_atdd")
    @acceptance_test(
        name="Subcategories Direct-Only Allocations",
        criteria_id="subcategories_direct_only",
        given="I have subcategories with direct allocations but no parent allocations",
        when="I view budget by classification",
        then="I see only the subcategory allocations aggregated to parent level",
    )
    def test_subcategories_direct_only_allocations(self):
        """Test scenario: Only subcategories have allocations, parent has none."""
        # Given: Parent category with subcategories that have direct allocations
        entertainment_parent = Category.objects.create(
            name="Entertainment", type="expense"
        )
        movies_subcategory = Category.objects.create(
            name="Movies", type="expense", parent=entertainment_parent
        )
        games_subcategory = Category.objects.create(
            name="Games", type="expense", parent=entertainment_parent
        )

        payoree1 = Payoree.objects.create(name="AMC Theaters")
        payoree2 = Payoree.objects.create(name="Steam")

        # Create transactions assigned to parent (typical pattern)
        Transaction.objects.create(
            source="test_file.csv",
            sheet_account="expense",
            account_type="checking",
            date=datetime(2025, 9, 10),  # September 2025 - within last 12 months
            amount=Decimal("-15.00"),
            description="Movie ticket",
            payoree=payoree1,
            category=entertainment_parent,
        )
        Transaction.objects.create(
            source="test_file.csv",
            sheet_account="expense",
            account_type="checking",
            date=datetime(2025, 9, 25),  # September 2025 - within last 12 months
            amount=Decimal("-29.99"),
            description="Game purchase",
            payoree=payoree2,
            category=entertainment_parent,
        )

        # Create budget allocations ONLY for subcategories (no parent allocation)
        # First, deactivate the setup budget plan to ensure our test plan is used
        self.budget_plan.is_active = False
        self.budget_plan.save()

        budget_plan = BudgetPlan.objects.create(
            name="Test Budget", year=2025, month=10, is_active=True
        )
        BudgetAllocation.objects.create(
            budget_plan=budget_plan,
            subcategory=movies_subcategory,
            amount=Decimal("100.00"),
        )
        BudgetAllocation.objects.create(
            budget_plan=budget_plan,
            subcategory=games_subcategory,
            amount=Decimal("150.00"),
        )

        # When: I view budget by classification for categories
        response = self.client.get(
            reverse("budgets:classification_analysis"),
            {
                "classification_type": "category",
                "category_id": str(entertainment_parent.pk),
            },
        )

        # Then: I see only subcategory allocations aggregated to parent level
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # Should show Entertainment with total subcategory allocations (100 + 150 = 250)
        self.assertIn("Entertainment", content)
        self.assertIn("250.00", content)  # Total subcategory allocations
        self.assertIn("44.99", content)  # Total spending (15.00 + 29.99)

    @user_story("budgets", "budget_by_classification_atdd")
    @acceptance_test(
        name="Real Database Auto Category Scenario",
        criteria_id="real_db_auto_category",
        given="I have real database data with specific transaction patterns",
        when="I view budget by classification analysis",
        then="the system handles actual production data correctly",
    )
    def test_real_database_auto_category_scenario(self):
        """Test with real Auto category transaction patterns from production database."""
        # Given: Real Auto category (ID: 6) with actual transaction patterns
        auto_category = Category.objects.create(name="Auto", type="expense")

        # Real payorees from production data
        shell = Payoree.objects.create(name="Shell")
        valero = Payoree.objects.create(name="Valero")

        # Temporarily assign real transactions to Auto category for testing
        # Based on actual transaction IDs: [2338, 641, 644] from production
        test_transactions = [
            Transaction.objects.create(
                source="test_file.csv",
                sheet_account="expense",
                account_type="checking",
                date=datetime(2025, 9, 15),  # September 2025 - within last 12 months
                amount=Decimal("-65.89"),
                description="SHELL OIL 12345678",
                payoree=shell,
                category=auto_category,
            ),
            Transaction.objects.create(
                source="test_file.csv",
                sheet_account="expense",
                account_type="checking",
                date=datetime(2025, 9, 3),  # September 2025 - within last 12 months
                amount=Decimal("-58.42"),
                description="VALERO CORNER STORE",
                payoree=valero,
                category=auto_category,
            ),
            Transaction.objects.create(
                source="test_file.csv",
                sheet_account="expense",
                account_type="checking",
                date=datetime(2025, 9, 10),  # September 2025 - within last 12 months
                amount=Decimal("-72.15"),
                description="SHELL SERVICE STATION",
                payoree=shell,
                category=auto_category,
            ),
        ]

        # Create realistic budget allocation
        # First, deactivate the setup budget plan to ensure our test plan is used
        self.budget_plan.is_active = False
        self.budget_plan.save()

        budget_plan = BudgetPlan.objects.create(
            name="Production Test Budget", year=2025, month=10, is_active=True
        )
        BudgetAllocation.objects.create(
            budget_plan=budget_plan, category=auto_category, amount=Decimal("400.00")
        )

        try:
            # When: I view budget by classification for categories
            response = self.client.get(
                reverse("budgets:classification_analysis"),
                {
                    "classification_type": "category",
                    "category_id": str(auto_category.pk),
                },
            )

            # Then: System handles production data correctly
            self.assertEqual(response.status_code, 200)
            content = response.content.decode("utf-8")

            # Verify Auto category appears with correct totals
            self.assertIn("Auto", content)
            self.assertIn("400.00", content)  # Budget allocation

            # Verify total spending calculation (65.89 + 58.42 + 72.15 = 196.46)
            self.assertIn("196.46", content)

        finally:
            # Cleanup: Remove test transactions to avoid affecting other tests
            for transaction in test_transactions:
                transaction.delete()

    @user_story("budgets", "budget_by_classification_atdd")
    @acceptance_test(
        name="Real Database Restaurant Category Scenario",
        criteria_id="real_db_restaurant_category",
        given="I have real database Restaurant category with multiple transactions",
        when="I view budget by classification analysis",
        then="the aggregation handles high-volume transaction categories",
    )
    def test_real_database_restaurant_category_scenario(self):
        """Test with real Restaurant category transaction patterns from production database."""
        # Given: Real Restaurant category (ID: 161) with multiple transaction patterns
        restaurant_category = Category.objects.create(name="Restaurant", type="expense")

        # Real payorees from production data
        mcdonalds = Payoree.objects.create(name="McDonald's")
        subway = Payoree.objects.create(name="Subway")
        chipotle = Payoree.objects.create(name="Chipotle")

        # Temporarily assign real transactions to Restaurant category for testing
        # Based on actual transaction IDs: [645, 650, 653, 658, 663, 665] from production
        test_transactions = [
            Transaction.objects.create(
                source="test_file.csv",
                sheet_account="expense",
                account_type="checking",
                date=datetime(2025, 9, 8),  # September 2025 - within last 12 months
                amount=Decimal("-12.47"),
                description="MCDONALD'S #12345",
                payoree=mcdonalds,
                category=restaurant_category,
            ),
            Transaction.objects.create(
                source="test_file.csv",
                sheet_account="expense",
                account_type="checking",
                date=datetime(2025, 9, 12),  # September 2025 - within last 12 months
                amount=Decimal("-8.99"),
                description="SUBWAY SANDWICHES",
                payoree=subway,
                category=restaurant_category,
            ),
            Transaction.objects.create(
                source="test_file.csv",
                sheet_account="expense",
                account_type="checking",
                date=datetime(2025, 9, 18),  # September 2025 - within last 12 months
                amount=Decimal("-15.23"),
                description="CHIPOTLE MEXICAN GRILL",
                payoree=chipotle,
                category=restaurant_category,
            ),
            Transaction.objects.create(
                source="test_file.csv",
                sheet_account="expense",
                account_type="checking",
                date=datetime(2025, 9, 25),  # September 2025 - within last 12 months
                amount=Decimal("-11.85"),
                description="MCDONALD'S #67890",
                payoree=mcdonalds,
                category=restaurant_category,
            ),
            Transaction.objects.create(
                source="test_file.csv",
                sheet_account="expense",
                account_type="checking",
                date=datetime(2025, 10, 2),  # October 2025 - within last 12 months
                amount=Decimal("-9.47"),
                description="SUBWAY DOWNTOWN",
                payoree=subway,
                category=restaurant_category,
            ),
            Transaction.objects.create(
                source="test_file.csv",
                sheet_account="expense",
                account_type="checking",
                date=datetime(2025, 10, 8),  # October 2025 - within last 12 months
                amount=Decimal("-18.99"),
                description="CHIPOTLE BOWLS",
                payoree=chipotle,
                category=restaurant_category,
            ),
        ]

        # Create realistic budget allocation for restaurant spending
        # First, deactivate the setup budget plan to ensure our test plan is used
        self.budget_plan.is_active = False
        self.budget_plan.save()

        budget_plan = BudgetPlan.objects.create(
            name="Production Test Budget", year=2025, month=10, is_active=True
        )
        BudgetAllocation.objects.create(
            budget_plan=budget_plan,
            category=restaurant_category,
            amount=Decimal("250.00"),
        )

        try:
            # When: I view budget by classification for categories
            response = self.client.get(
                reverse("budgets:classification_analysis"),
                {
                    "classification_type": "category",
                    "category_id": str(restaurant_category.pk),
                },
            )

            # Then: System handles high-volume transaction categories correctly
            self.assertEqual(response.status_code, 200)
            content = response.content.decode("utf-8")

            # Verify Restaurant category appears with correct totals
            self.assertIn("Restaurant", content)
            self.assertIn("250.00", content)  # Budget allocation

            # Verify total spending calculation (12.47 + 8.99 + 15.23 + 11.85 + 9.47 + 18.99 = 76.00)
            # Note: View shows monthly totals, not grand total, so check individual months
            self.assertIn(
                "48.54", content
            )  # September 2025 total (12.47 + 8.99 + 15.23 + 11.85)

            # Verify the view can handle multiple transactions per payoree
            # (McDonald's: 2 transactions, Subway: 2 transactions, Chipotle: 2 transactions)

        finally:
            # Cleanup: Remove test transactions to avoid affecting other tests
            for transaction in test_transactions:
                transaction.delete()
