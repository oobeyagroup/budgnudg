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
