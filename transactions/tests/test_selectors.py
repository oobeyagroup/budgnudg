import datetime as dt
from decimal import Decimal
import pytest
from django.utils import timezone
from transactions.models import Transaction, Payoree, RecurringSeries
from transactions.selectors import build_upcoming_forecast


@pytest.mark.django_db
def test_selector_suggests_recurring_when_no_series():
    # create three monthly transactions for "Alpha Merchant"
    pay = Payoree.objects.create(name="Alpha Pay")
    base = timezone.now().date() - dt.timedelta(days=90)
    for i in range(3):
        Transaction.objects.create(
            source="test",
            bank_account=None,
            sheet_account="checking",
            date=base + dt.timedelta(days=30 * i),
            description="Alpha Merchant Purchase",
            amount=Decimal("-15.00"),
            account_type="checking",
            payoree=pay,
        )

    forecast = build_upcoming_forecast(weeks=4, lookback_weeks=52, min_recurring=3)
    # detector should suggest at least one recurring prediction
    assert isinstance(forecast, dict)
    assert len(forecast.get("recurring_predictions", [])) >= 1
    # none should be in designated_recurring
    assert len(forecast.get("designated_recurring", [])) == 0


@pytest.mark.django_db
def test_selector_marks_designated_when_series_exists():
    # create three monthly transactions for "Beta Merchant"
    pay = Payoree.objects.create(name="Beta Pay")
    base = timezone.now().date() - dt.timedelta(days=90)
    for i in range(3):
        Transaction.objects.create(
            source="test",
            bank_account=None,
            sheet_account="checking",
            date=base + dt.timedelta(days=30 * i),
            description="Beta Merchant Charge",
            amount=Decimal("-20.00"),
            account_type="checking",
            payoree=pay,
        )

    # create a RecurringSeries that should match by payoree name
    series = RecurringSeries.objects.create(
        payoree=pay,
        amount_cents=2000,
        interval="monthly",
        confidence=0.9,
        first_seen=base,
        last_seen=base + dt.timedelta(days=60),
        next_due=timezone.now().date()
        + dt.timedelta(days=14),  # Explicitly set next_due in range
        active=True,
    )

    forecast = build_upcoming_forecast(weeks=4, lookback_weeks=16)
    # since a designated series exists, it should appear under designated_recurring
    assert len(forecast.get("designated_recurring", [])) >= 1
    # and not be in the suggested recurring_predictions
    assert len(forecast.get("recurring_predictions", [])) == 0


@pytest.mark.django_db
def test_selector_detects_weekly_and_biweekly_frequencies():
    pay = Payoree.objects.create(name="Gamma Pay")
    base = timezone.now().date() - dt.timedelta(days=28)
    # weekly pattern: 0,7,14 days
    for i in range(3):
        Transaction.objects.create(
            source="test",
            bank_account=None,
            sheet_account="checking",
            date=base + dt.timedelta(days=7 * i),
            description="Gamma Weekly",
            amount=Decimal("-5.00"),
            account_type="checking",
            payoree=pay,
        )

    # biweekly pattern: separate description
    pay2 = Payoree.objects.create(name="Delta Pay")
    base2 = timezone.now().date() - dt.timedelta(days=42)
    for i in range(3):
        Transaction.objects.create(
            source="test",
            bank_account=None,
            sheet_account="checking",
            date=base2 + dt.timedelta(days=14 * i),
            description="Delta Biweekly",
            amount=Decimal("-8.00"),
            account_type="checking",
            payoree=pay2,
        )

    forecast = build_upcoming_forecast(weeks=4, lookback_weeks=52, min_recurring=3)
    recs = forecast.get("recurring_predictions", [])
    freqs = {r.get("freq_days") for r in recs}
    # expect to see weekly (7) and biweekly (14) detected
    assert 7 in freqs or 14 in freqs


@pytest.mark.django_db
def test_selector_median_edge_cases():
    pay = Payoree.objects.create(name="Edge Pay")

    # helper to run with given deltas list (days between transactions)
    def make_txns(deltas):
        Transaction.objects.all().delete()
        # Start far enough in the past to keep last_tx near today
        base = timezone.now().date() - dt.timedelta(days=sum(deltas))
        desc = "Edge Merchant"
        cur = base
        # create first transaction at base
        Transaction.objects.create(
            source="test",
            bank_account=None,
            sheet_account="checking",
            date=cur,
            description=desc,
            amount=Decimal("-7.00"),
            account_type="checking",
            payoree=pay,
        )
        # then create subsequent transactions by advancing cur by each delta
        for delta in deltas:
            cur = cur + dt.timedelta(days=delta)
            Transaction.objects.create(
                source="test",
                bank_account=None,
                sheet_account="checking",
                date=cur,
                description=desc,
                amount=Decimal("-7.00"),
                account_type="checking",
                payoree=pay,
            )

    # deltas that should yield median 5 -> weekly
    make_txns([5, 5])
    f1 = build_upcoming_forecast(weeks=4, lookback_weeks=52, min_recurring=3)
    freqs1 = {r.get("freq_days") for r in f1.get("recurring_predictions", [])}
    assert 7 in freqs1

    # deltas that yield median 10 -> weekly
    make_txns([10, 10])
    f2 = build_upcoming_forecast(weeks=4, lookback_weeks=52, min_recurring=3)
    freqs2 = {r.get("freq_days") for r in f2.get("recurring_predictions", [])}
    assert 7 in freqs2

    # deltas that yield median 11 -> biweekly
    make_txns([11, 11])
    f3 = build_upcoming_forecast(weeks=4, lookback_weeks=52, min_recurring=3)
    freqs3 = {r.get("freq_days") for r in f3.get("recurring_predictions", [])}
    assert 14 in freqs3

    # deltas that yield median 18 -> biweekly
    make_txns([18, 18])
    f4 = build_upcoming_forecast(weeks=4, lookback_weeks=52, min_recurring=3)
    freqs4 = {r.get("freq_days") for r in f4.get("recurring_predictions", [])}
    assert 14 in freqs4

    # deltas that yield median 19 -> should be skipped (irregular)
    make_txns([19, 19])
    f5 = build_upcoming_forecast(weeks=4, lookback_weeks=52, min_recurring=3)
    freqs5 = {r.get("freq_days") for r in f5.get("recurring_predictions", [])}
    # expect no detection for this irregular median
    assert 7 not in freqs5 and 14 not in freqs5 and 30 not in freqs5


@pytest.mark.django_db
def test_recurring_series_model_creation():
    """Test that RecurringSeries can be created and next_due is auto-calculated."""
    from transactions.models import Category

    payoree = Payoree.objects.create(name="Test Payoree")
    category = Category.objects.create(name="Test Category", type="expense")

    # Create transactions to establish a baseline
    base_date = timezone.now().date() - dt.timedelta(days=30)
    for i in range(3):
        Transaction.objects.create(
            source="test",
            bank_account=None,
            sheet_account="checking",
            date=base_date + dt.timedelta(days=i * 10),
            description=f"Test transaction {i+1}",
            amount=Decimal("-10.00"),
            account_type="checking",
            payoree=payoree,
            category=category,
        )

    # Create RecurringSeries
    series = RecurringSeries.objects.create(
        payoree=payoree,
        amount_cents=1000,  # $10.00
        interval="monthly",
        first_seen=base_date,
        last_seen=base_date + dt.timedelta(days=20),
        active=True,
    )

    # Check that next_due was auto-calculated
    assert series.next_due is not None
    assert series.next_due > base_date + dt.timedelta(days=20)


@pytest.mark.django_db
def test_recurring_series_model_creation():
    """Test that RecurringSeries can be created and next_due is auto-calculated."""
    from transactions.models import Category

    payoree = Payoree.objects.create(name="Unique Test Payoree")
    category = Category.objects.create(name="Test Category", type="expense")

    # Create transactions to establish a baseline
    base_date = timezone.now().date() - dt.timedelta(days=30)
    for i in range(3):
        Transaction.objects.create(
            source="test",
            bank_account=None,
            sheet_account="checking",
            date=base_date + dt.timedelta(days=i * 10),
            description=f"Test transaction {i+1}",
            amount=Decimal("-10.00"),
            account_type="checking",
            payoree=payoree,
            category=category,
        )

    # Create RecurringSeries
    series = RecurringSeries.objects.create(
        payoree=payoree,
        amount_cents=1000,  # $10.00
        interval="monthly",
        first_seen=base_date,
        last_seen=base_date + dt.timedelta(days=20),
        active=True,
    )

    # Check that next_due was auto-calculated
    assert series.next_due is not None
    assert series.next_due > base_date + dt.timedelta(days=20)

    # Check string representation - just check that it's not the default object string
    str_repr = str(series)
    assert (
        "RecurringSeries object" not in str_repr
    )  # Should not be the default Django string


@pytest.mark.django_db
def test_recurring_series_next_due_calculation():
    """Test that next_due is correctly calculated for different intervals."""
    payoree = Payoree.objects.create(name="Test Payoree")
    base_date = timezone.now().date()

    # Test monthly interval
    monthly_series = RecurringSeries.objects.create(
        payoree=payoree,
        amount_cents=2000,
        interval="monthly",
        first_seen=base_date,
        active=True,
    )
    expected_monthly = base_date + dt.timedelta(days=30)
    assert monthly_series.next_due == expected_monthly

    # Test weekly interval
    weekly_series = RecurringSeries.objects.create(
        payoree=Payoree.objects.create(name="Weekly Payoree"),
        amount_cents=500,
        interval="weekly",
        first_seen=base_date,
        active=True,
    )
    expected_weekly = base_date + dt.timedelta(days=7)
    assert weekly_series.next_due == expected_weekly


@pytest.mark.django_db
def test_designated_recurring_series_in_forecast():
    """Test that designated RecurringSeries appear in forecast with correct labels."""
    from transactions.models import Category

    # Create payoree and category
    payoree = Payoree.objects.create(name="Designated Payoree")
    category = Category.objects.create(name="Test Category", type="expense")

    # Create transactions for the payoree
    base_date = timezone.now().date() - dt.timedelta(days=30)
    for i in range(3):
        Transaction.objects.create(
            source="test",
            bank_account=None,
            sheet_account="checking",
            date=base_date + dt.timedelta(days=i * 10),
            description=f"Designated transaction {i+1}",
            amount=Decimal("-15.00"),
            account_type="checking",
            payoree=payoree,
            category=category,
        )

    # Create RecurringSeries with next_due in forecast range
    forecast_start = timezone.now().date() + dt.timedelta(days=7)
    series = RecurringSeries.objects.create(
        payoree=payoree,
        amount_cents=1500,
        interval="monthly",
        first_seen=base_date,
        last_seen=base_date + dt.timedelta(days=20),
        next_due=forecast_start,
        active=True,
    )

    # Test forecast
    forecast = build_upcoming_forecast(weeks=4, lookback_weeks=4)

    # Check designated recurring
    designated = forecast.get("designated_recurring", [])
    assert len(designated) == 1

    designated_item = designated[0]
    assert designated_item["payoree"] == "Designated Payoree"
    assert designated_item["amount"] == 15.0  # cents to dollars
    assert designated_item["next_date"] == forecast_start
    assert "(Designated)" in designated_item["description"]
    assert designated_item["description"] == "Designated Payoree (Designated)"


@pytest.mark.django_db
def test_designated_series_appear_in_daily_transactions():
    """Test that designated RecurringSeries appear in daily transaction projections."""
    from transactions.models import Category

    # Create payoree and category
    payoree = Payoree.objects.create(name="Daily Test Payoree")
    category = Category.objects.create(name="Test Category", type="expense")

    # Create transactions
    base_date = timezone.now().date() - dt.timedelta(days=30)
    for i in range(3):
        Transaction.objects.create(
            source="test",
            bank_account=None,
            sheet_account="checking",
            date=base_date + dt.timedelta(days=i * 10),
            description=f"Daily test transaction {i+1}",
            amount=Decimal("-12.00"),
            account_type="checking",
            payoree=payoree,
            category=category,
        )

    # Create RecurringSeries with next_due in forecast range
    next_due_date = timezone.now().date() + dt.timedelta(days=10)
    series = RecurringSeries.objects.create(
        payoree=payoree,
        amount_cents=1200,
        interval="monthly",
        first_seen=base_date,
        last_seen=base_date + dt.timedelta(days=20),
        next_due=next_due_date,
        active=True,
    )

    # Test forecast
    forecast = build_upcoming_forecast(weeks=4, lookback_weeks=4)
    daily_txns = forecast.get("daily_transactions", {})

    # Find the designated transaction in daily transactions
    designated_found = False
    for date_key, txns in daily_txns.items():
        for txn in txns:
            if "(Designated)" in str(txn.get("description", "")):
                designated_found = True
                assert txn["date"] == next_due_date
                assert txn["payoree"] == "Daily Test Payoree"
                assert (
                    txn["amount"] == 12.0
                )  # cents to dollars, positive for designated series
                assert txn["description"] == "Daily Test Payoree (Designated)"
                break
        if designated_found:
            break

    assert (
        designated_found
    ), "Designated RecurringSeries not found in daily transactions"


@pytest.mark.django_db
def test_recurring_series_date_filtering():
    """Test that RecurringSeries are properly filtered by forecast date range."""
    from transactions.models import Category

    payoree = Payoree.objects.create(name="Date Filter Payoree")
    category = Category.objects.create(name="Test Category", type="expense")

    # Create transactions
    base_date = timezone.now().date() - dt.timedelta(days=30)
    Transaction.objects.create(
        source="test",
        bank_account=None,
        sheet_account="checking",
        date=base_date,
        description="Date filter transaction",
        amount=Decimal("-8.00"),
        account_type="checking",
        payoree=payoree,
        category=category,
    )

    # Create series with next_due outside forecast range (too far in future)
    far_future_date = timezone.now().date() + dt.timedelta(days=100)
    series = RecurringSeries.objects.create(
        payoree=payoree,
        amount_cents=800,
        interval="monthly",
        first_seen=base_date,
        next_due=far_future_date,
        active=True,
    )

    # Test forecast - series should not appear because next_due is too far in future
    forecast = build_upcoming_forecast(weeks=4, lookback_weeks=8)
    designated = forecast.get("designated_recurring", [])
    assert (
        len(designated) == 0
    ), "Series with far future next_due should not appear in forecast"

    # Update next_due to be within forecast range
    within_range_date = timezone.now().date() + dt.timedelta(days=14)
    series.next_due = within_range_date
    series.save()

    # Test forecast again - series should now appear
    forecast = build_upcoming_forecast(weeks=4, lookback_weeks=8)
    designated = forecast.get("designated_recurring", [])
    assert (
        len(designated) == 1
    ), "Series with next_due in range should appear in forecast"


@pytest.mark.django_db
def test_inactive_recurring_series_not_in_forecast():
    """Test that inactive RecurringSeries do not appear in forecast."""
    from transactions.models import Category

    payoree = Payoree.objects.create(name="Inactive Payoree")
    category = Category.objects.create(name="Test Category", type="expense")

    # Create transaction
    base_date = timezone.now().date() - dt.timedelta(days=30)
    Transaction.objects.create(
        source="test",
        bank_account=None,
        sheet_account="checking",
        date=base_date,
        description="Inactive test transaction",
        amount=Decimal("-5.00"),
        account_type="checking",
        payoree=payoree,
        category=category,
    )

    # Create inactive RecurringSeries
    next_due_date = timezone.now().date() + dt.timedelta(days=7)
    RecurringSeries.objects.create(
        payoree=payoree,
        amount_cents=500,
        interval="weekly",
        first_seen=base_date,
        next_due=next_due_date,
        active=False,  # Inactive
    )

    # Test forecast - inactive series should not appear
    forecast = build_upcoming_forecast(weeks=4, lookback_weeks=4)
    designated = forecast.get("designated_recurring", [])
    assert (
        len(designated) == 0
    ), "Inactive RecurringSeries should not appear in forecast"
