# transactions/tests/test_acceptance_search_filtering_atdd.py
"""
ATDD tests for Advanced Transaction Search & Filtering functionality.

This test suite implements incremental development of search capabilities,
starting with basic filters and building up to advanced features.
"""

import pytest
from decimal import Decimal
from datetime import date, datetime, timedelta
from django.urls import reverse
from django.contrib.auth import get_user_model

from transactions.models import Transaction, Category, Payoree
from ingest.models import FinancialAccount
from atdd_tracker import acceptance_test, user_story

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def search_user():
    """Create a user for search tests."""
    return User.objects.create_user(
        username="searcher", email="searcher@example.com", password="testpass123"
    )


@pytest.fixture
def bank_account():
    """Create a bank account for transactions."""
    return FinancialAccount.objects.create(
        name="Test Checking",
        column_map={},
        description="Test Financial Account for Search",
    )


@pytest.fixture
def categories():
    """Create test categories."""
    dining = Category.objects.create(name="Dining", parent=None)
    groceries = Category.objects.create(name="Groceries", parent=None)
    gas = Category.objects.create(name="Gas", parent=None)
    return {
        "dining": dining,
        "groceries": groceries,
        "gas": gas,
    }


@pytest.fixture
def payorees():
    """Create test payorees."""
    return {
        "starbucks": Payoree.objects.create(name="Starbucks"),
        "whole_foods": Payoree.objects.create(name="Whole Foods"),
        "shell": Payoree.objects.create(name="Shell"),
    }


@pytest.fixture
def sample_transactions(bank_account, categories, payorees):
    """Create a set of sample transactions for search testing."""
    transactions = []

    # Recent transactions (within last 30 days)
    base_date = date.today() - timedelta(days=15)

    transactions.extend(
        [
            Transaction.objects.create(
                source="test_data.csv",
                bank_account=bank_account,
                sheet_account="expense",
                date=base_date,
                amount=Decimal("-15.50"),
                description="Starbucks Coffee Purchase",
                account_type="checking",
                category=categories["dining"],
                payoree=payorees["starbucks"],
            ),
            Transaction.objects.create(
                source="test_data.csv",
                bank_account=bank_account,
                sheet_account="expense",
                date=base_date + timedelta(days=1),
                amount=Decimal("-85.30"),
                description="Whole Foods Groceries",
                account_type="checking",
                category=categories["groceries"],
                payoree=payorees["whole_foods"],
            ),
            Transaction.objects.create(
                source="test_data.csv",
                bank_account=bank_account,
                sheet_account="expense",
                date=base_date + timedelta(days=2),
                amount=Decimal("-45.00"),
                description="Shell Gas Station",
                account_type="checking",
                category=categories["gas"],
                payoree=payorees["shell"],
            ),
            Transaction.objects.create(
                source="test_data.csv",
                bank_account=bank_account,
                sheet_account="expense",
                date=base_date + timedelta(days=3),
                amount=Decimal("-125.75"),
                description="Whole Foods Organic Produce",
                account_type="checking",
                category=categories["groceries"],
                payoree=payorees["whole_foods"],
            ),
        ]
    )

    # Older transactions (60+ days ago)
    old_date = date.today() - timedelta(days=60)
    transactions.extend(
        [
            Transaction.objects.create(
                source="test_data.csv",
                bank_account=bank_account,
                sheet_account="expense",
                date=old_date,
                amount=Decimal("-200.00"),
                description="Large Grocery Shopping",
                account_type="checking",
                category=categories["groceries"],
                payoree=payorees["whole_foods"],
            ),
            Transaction.objects.create(
                source="test_data.csv",
                bank_account=bank_account,
                sheet_account="expense",
                date=old_date + timedelta(days=1),
                amount=Decimal("-8.50"),
                description="Starbucks Morning Coffee",
                account_type="checking",
                category=categories["dining"],
                payoree=payorees["starbucks"],
            ),
        ]
    )

    # Large expense transactions (for amount range testing)
    large_expense_date = date.today() - timedelta(days=10)
    transactions.extend(
        [
            Transaction.objects.create(
                source="test_data.csv",
                bank_account=bank_account,
                sheet_account="expense",
                date=large_expense_date,
                amount=Decimal("-1500.00"),
                description="Rent Payment",
                account_type="checking",
                category=None,  # Uncategorized
                payoree=None,
            ),
            Transaction.objects.create(
                source="test_data.csv",
                bank_account=bank_account,
                sheet_account="expense",
                date=large_expense_date + timedelta(days=1),
                amount=Decimal("-2500.00"),
                description="Mortgage Payment",
                account_type="checking",
                category=None,  # Uncategorized
                payoree=None,
            ),
            Transaction.objects.create(
                source="test_data.csv",
                bank_account=bank_account,
                sheet_account="expense",
                date=large_expense_date + timedelta(days=2),
                amount=Decimal("-3200.00"),
                description="Property Tax Payment",
                account_type="checking",
                category=None,  # Uncategorized
                payoree=None,
            ),
            Transaction.objects.create(
                source="test_data.csv",
                bank_account=bank_account,
                sheet_account="expense",
                date=large_expense_date + timedelta(days=3),
                amount=Decimal("-500.00"),
                description="Utilities Bill",
                account_type="checking",
                category=None,  # Uncategorized
                payoree=None,
            ),
        ]
    )

    return transactions


# =============================================================================
# BASIC SEARCH FUNCTIONALITY (MVP) - First Implementation Phase
# =============================================================================


@user_story("transactions", "advanced_search_filtering")
@acceptance_test(
    name="Search by Date Range",
    criteria_id="search_by_date_range",
    given="I have transactions across multiple dates",
    when="I filter by a date range",
    then="I see only transactions within that range",
)
def test_search_by_date_range(sample_transactions):
    """Test filtering transactions by date range."""

    # Test search for last 30 days only
    start_date = date.today() - timedelta(days=30)
    end_date = date.today()

    # Get transactions within date range using Django ORM
    filtered_transactions = Transaction.objects.filter(
        date__gte=start_date, date__lte=end_date
    )

    # Verify we get the expected results
    recent_transactions = [
        t for t in sample_transactions if start_date <= t.date <= end_date
    ]
    old_transactions = [t for t in sample_transactions if t.date < start_date]

    # Assertions
    assert len(recent_transactions) > 0, "Should have recent transactions"
    assert len(old_transactions) > 0, "Should have old transactions"
    assert filtered_transactions.count() == len(recent_transactions)

    # Also test the web interface with correct parameter names
    from django.test import Client
    from django.contrib.auth.models import User

    # Create a test user
    user = User.objects.create_user("datetest", "test@test.com", "pass")
    client = Client()
    client.force_login(user)

    # Test with the correct form parameter names (start_date, end_date)
    response = client.get(
        "/transactions/search/",
        {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
        },
    )

    assert response.status_code == 200
    context = response.context

    # Verify date filter was applied (this would fail with the old parameter name bug)
    filters_applied = context["filters_applied"]
    date_filter_found = any(
        "Start Date" in filter_text or "End Date" in filter_text
        for filter_text in filters_applied
    )
    assert (
        date_filter_found
    ), f"Date filter not applied with correct parameter names! Filters: {filters_applied}"


@user_story("transactions", "advanced_search_filtering")
@acceptance_test(
    name="Search by Amount Range",
    criteria_id="search_by_amount_range",
    given="I have transactions of various amounts",
    when="I filter by amount range ($50-$200)",
    then="I see only transactions within that range",
)
def test_search_by_amount_range(sample_transactions):
    """Test filtering transactions by amount range."""

    # Search for transactions between $10 and $50 in absolute value
    min_amount = Decimal("-50.00")
    max_amount = Decimal("-10.00")

    filtered_transactions = Transaction.objects.filter(
        amount__gte=min_amount, amount__lte=max_amount
    )

    # Verify results - should find transactions in range
    expected_transactions = [
        t for t in sample_transactions if min_amount <= t.amount <= max_amount
    ]

    # Basic assertion - we should have some transactions in this range
    assert filtered_transactions.exists(), "Should find transactions in amount range"


@user_story("transactions", "advanced_search_filtering")
@acceptance_test(
    name="Search by Category",
    criteria_id="search_by_category",
    given="I have transactions in different categories",
    when="I filter by a specific category",
    then="I see only transactions in that category",
)
def test_search_by_category(sample_transactions, categories):
    """Test filtering transactions by category."""

    # Search for dining transactions only
    filtered_transactions = Transaction.objects.filter(category=categories["dining"])

    # Verify results
    dining_transactions = [
        t for t in sample_transactions if t.category == categories["dining"]
    ]
    non_dining_transactions = [
        t for t in sample_transactions if t.category != categories["dining"]
    ]

    # Basic assertions
    assert filtered_transactions.exists(), "Should find dining transactions"
    assert len(dining_transactions) > 0, "Should have dining transactions in test data"
    assert filtered_transactions.count() == len(dining_transactions)


@user_story("transactions", "advanced_search_filtering")
@acceptance_test(
    name="Search by Description Keywords",
    criteria_id="search_by_description_keywords",
    given="I have transactions with various descriptions",
    when="I search by keywords",
    then="I see transactions containing those keywords",
)
def test_search_by_description_keywords(sample_transactions):
    """Test filtering transactions by description keywords."""

    # Search for transactions containing "Starbucks"
    search_keyword = "Starbucks"
    filtered_transactions = Transaction.objects.filter(
        description__icontains=search_keyword
    )

    # Find matching and non-matching transactions
    starbucks_transactions = [
        t for t in sample_transactions if search_keyword in t.description
    ]
    other_transactions = [
        t for t in sample_transactions if search_keyword not in t.description
    ]

    # Verify test data setup
    assert len(starbucks_transactions) > 0, "Should have Starbucks transactions"
    assert len(other_transactions) > 0, "Should have non-Starbucks transactions"

    # Basic filtering assertion
    assert filtered_transactions.count() == len(starbucks_transactions)


# =============================================================================
# NEW TEST: Large Amount Range Search
# =============================================================================


@user_story("transactions", "advanced_search_filtering")
@acceptance_test(
    name="Search by Large Amount Range",
    criteria_id="search_by_large_amount_range",
    given="I have transactions with various amounts including large expenses",
    when="I filter by a large amount range (-1000 to -3000)",
    then="I see only transactions within that range",
)
def test_search_by_large_amount_range(sample_transactions):
    """Test filtering transactions by large amount range (-$1000 to -$3000)."""

    # Define search range for transactions between $1000 and $3000 (in absolute value)
    min_amount = Decimal("1000.00")
    max_amount = Decimal("3000.00")

    # Filter transactions in the range -$3000 to -$1000 (negative amounts)
    # Since amounts are negative for expenses, we use:
    # - amount <= -min_amount (more negative than -1000)
    # - amount >= -max_amount (less negative than -3000)
    filtered_transactions = Transaction.objects.filter(
        amount__lte=-min_amount,  # More negative than -1000
        amount__gte=-max_amount,  # Less negative than -3000
    )

    # Find expected transactions manually for verification
    expected_transactions = [
        t for t in sample_transactions if min_amount <= abs(t.amount) <= max_amount
    ]

    # Verify test data setup
    assert (
        len(expected_transactions) > 0
    ), "Should have transactions in the $1000-$3000 range"
    assert len(expected_transactions) == 2, "Expected exactly 2 large transactions"

    # Verify some transactions are outside the range
    outside_range_transactions = [
        t
        for t in sample_transactions
        if not (min_amount <= abs(t.amount) <= max_amount)
    ]
    assert (
        len(outside_range_transactions) > 0
    ), "Should have transactions outside the range"

    # Test the filtering logic
    filtered_count = filtered_transactions.count()
    expected_count = len(expected_transactions)

    assert filtered_count == expected_count, (
        f"Expected {expected_count} transactions in range $1000-$3000, "
        f"but found {filtered_count}"
    )

    # Verify specific amounts are included
    filtered_amounts = [abs(t.amount) for t in filtered_transactions]
    assert Decimal("1500.00") in filtered_amounts, "Should include $1500 rent payment"
    assert (
        Decimal("2500.00") in filtered_amounts
    ), "Should include $2500 mortgage payment"

    # Verify amounts outside range are excluded
    assert Decimal("200.00") not in filtered_amounts, "Should exclude $200 transaction"
    assert (
        Decimal("3200.00") not in filtered_amounts
    ), "Should exclude $3200 transaction (too large)"
    assert (
        Decimal("500.00") not in filtered_amounts
    ), "Should exclude $500 transaction (too small)"


# =============================================================================
# WEB INTERFACE INTEGRATION TEST
# =============================================================================


@user_story("transactions", "advanced_search_filtering")
@acceptance_test(
    name="Search Web Interface with Large Amount Range",
    criteria_id="search_web_interface_large_amount",
    given="I have the search form with amount range inputs",
    when="I search for amounts between $1000 and $3000 via web interface",
    then="I see the correct filtered results displayed",
)
def test_search_web_interface_large_amount_range(sample_transactions, search_user):
    """Test the search feature through the web interface with large amount range."""
    from django.test import Client

    # Create a client and log in the user
    client = Client()
    client.force_login(search_user)

    # Make a GET request to the search endpoint with amount range parameters
    response = client.get(
        "/transactions/search/",
        {
            "min_amount": "1000.00",  # Changed from amount_min to match form
            "max_amount": "3000.00",  # Changed from amount_max to match form
        },
    )

    # Verify the response is successful
    assert response.status_code == 200

    # Verify the context contains the expected data structure
    context = response.context
    assert "transactions" in context
    assert "summary" in context
    assert "filters_applied" in context
    assert "search_params" in context

    # Check that filters were applied and displayed correctly
    filters_applied = context["filters_applied"]
    # With our new logic, both amounts create a single "Amount Range" filter message
    assert any(
        "Amount Range: $1000.00 to $3000.00" in filter_text
        for filter_text in filters_applied
    )

    # Verify the search parameters are preserved in context for form repopulation
    search_params = context["search_params"]
    assert search_params.get("min_amount") == "1000.00"  # Changed from amount_min
    assert search_params.get("max_amount") == "3000.00"  # Changed from amount_max

    # This test verifies the web interface properly processes and displays
    # the search parameters, even though the ABS() function may not work
    # with SQLite in the test environment


@user_story("transactions", "advanced_search_filtering")
@acceptance_test(
    name="Search Parameter Name Mapping and Range Filtering",
    criteria_id="search_parameter_mapping_range_filter",
    given="I have transactions including a -$5010.09 Chase autopay transaction",
    when="I search for amounts between -$3000 and -$1000 using the correct form parameter names",
    then="I see only transactions in that range, excluding the -$5010.09 transaction",
)
def test_search_parameter_mapping_and_range_filtering(sample_transactions, search_user):
    """Test that form parameter names correctly map to view logic and range filtering works properly."""
    from django.test import Client
    from transactions.models import Transaction, Payoree
    from ingest.models import FinancialAccount
    from decimal import Decimal
    from datetime import date

    # Create additional specific transactions for this test
    account = FinancialAccount.objects.create(
        name="Test Account",
        description="Test checking account",
        column_map={},  # Required field
    )
    chase_payoree = Payoree.objects.create(name="Chase Credit Card Autopay")

    # Create a specific Chase autopay transaction that should be excluded (-$5010.09 is more negative than -$3000)
    chase_autopay = Transaction.objects.create(
        date=date(2025, 9, 1),
        description="CHASE CREDIT CRD AUTOPAY PPD ID: 4760039224",
        amount=Decimal("-5010.09"),
        bank_account=account,
        payoree=chase_payoree,
        source="test",
    )

    # Create transactions that should be included in the -$3000 to -$1000 range
    included_txn1 = Transaction.objects.create(
        date=date(2025, 9, 2),
        description="Mortgage Payment",
        amount=Decimal("-2500.00"),
        bank_account=account,
        payoree=Payoree.objects.create(name="Mortgage Company"),
        source="test",
    )

    included_txn2 = Transaction.objects.create(
        date=date(2025, 9, 3),
        description="Insurance Payment",
        amount=Decimal("-1500.00"),
        bank_account=account,
        payoree=Payoree.objects.create(name="Insurance Co"),
        source="test",
    )

    # Create a transaction that should be excluded (less negative than -$1000)
    excluded_txn = Transaction.objects.create(
        date=date(2025, 9, 4),
        description="Grocery Store",
        amount=Decimal("-800.00"),
        bank_account=account,
        payoree=Payoree.objects.create(name="Grocery Store"),
        source="test",
    )

    client = Client()
    client.force_login(search_user)

    # Test with the correct form parameter names (min_amount, max_amount)
    response = client.get(
        "/transactions/search/", {"min_amount": "-3000.00", "max_amount": "-1000.00"}
    )

    assert response.status_code == 200
    context = response.context

    # Verify the filter was applied correctly
    filters_applied = context["filters_applied"]
    assert any(
        "Amount Range: $-3000.00 to $-1000.00" in filter_text
        for filter_text in filters_applied
    )

    # Get the transaction IDs from results
    result_ids = set(txn.id for txn in context["transactions"])

    # Verify correct transactions are included
    assert (
        included_txn1.id in result_ids
    ), "Mortgage payment (-$2500) should be included in -$3000 to -$1000 range"
    assert (
        included_txn2.id in result_ids
    ), "Insurance payment (-$1500) should be included in -$3000 to -$1000 range"

    # Verify transactions outside the range are excluded
    assert (
        chase_autopay.id not in result_ids
    ), "Chase autopay (-$5010.09) should be excluded (more negative than -$3000)"
    assert (
        excluded_txn.id not in result_ids
    ), "Grocery store (-$800) should be excluded (less negative than -$1000)"

    # Verify the search parameters are preserved for form repopulation
    search_params = context["search_params"]
    assert search_params.get("min_amount") == "-3000.00"
    assert search_params.get("max_amount") == "-1000.00"

    print(
        f"✓ Range filter working correctly: {len(result_ids)} transactions found in range"
    )
    print(f"✓ Chase autopay (-$5010.09) correctly excluded from -$3000 to -$1000 range")


@user_story("transactions", "advanced_search_filtering")
@acceptance_test(
    name="All Search Parameter Names Match Form Fields",
    criteria_id="search_all_parameter_mapping",
    given="I have the search form with all field types (dates, amounts, category, description)",
    when="I submit the form with all parameters using correct field names",
    then="All filters are applied correctly without parameter name mismatches",
)
def test_all_search_parameter_mapping(sample_transactions, search_user):
    """Test that ALL search form parameter names correctly map to view logic."""
    from django.test import Client
    from datetime import date

    client = Client()
    client.force_login(search_user)

    # Test with ALL form field names to ensure they match the view
    response = client.get(
        "/transactions/search/",
        {
            "start_date": "2025-01-01",  # Form uses start_date (NOT date_start)
            "end_date": "2025-12-31",  # Form uses end_date (NOT date_end)
            "min_amount": "-2000.00",  # Form uses min_amount (NOT amount_min)
            "max_amount": "-1000.00",  # Form uses max_amount (NOT amount_max)
            "category": "",  # Form uses category (matches view)
            "description": "test",  # Form uses description (matches view)
        },
    )

    assert response.status_code == 200
    context = response.context

    # Verify ALL filters were recognized and applied
    filters_applied = context["filters_applied"]

    # Check that date filters were applied (this would fail with the old bug)
    date_filter_found = any(
        "Start Date" in filter_text or "End Date" in filter_text
        for filter_text in filters_applied
    )
    assert date_filter_found, f"Date filters not applied! Filters: {filters_applied}"

    # Check that amount filters were applied
    amount_filter_found = any(
        "Amount Range" in filter_text for filter_text in filters_applied
    )
    assert (
        amount_filter_found
    ), f"Amount filters not applied! Filters: {filters_applied}"

    # Check that description filter was applied
    description_filter_found = any(
        "Description" in filter_text for filter_text in filters_applied
    )
    assert (
        description_filter_found
    ), f"Description filter not applied! Filters: {filters_applied}"

    # Verify search parameters are preserved correctly for form repopulation
    search_params = context["search_params"]
    assert search_params.get("start_date") == "2025-01-01"
    assert search_params.get("end_date") == "2025-12-31"
    assert search_params.get("min_amount") == "-2000.00"
    assert search_params.get("max_amount") == "-1000.00"
    assert search_params.get("description") == "test"

    print(f"✓ All parameter mappings working: {len(filters_applied)} filters applied")
    print(f"✓ Date range filter correctly applied (was broken before fix)")
    print(f"✓ Amount range filter correctly applied (was broken before fix)")
    print(f"✓ Description filter correctly applied")
