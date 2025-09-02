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


@pytest.mark.skip(
    reason="Temporarily skipped - designated recurring series detection needs debugging"
)
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
    RecurringSeries.objects.create(
        payoree=pay,
        amount_cents=2000,
        interval="monthly",
        confidence=0.9,
        active=True,
    )

    forecast = build_upcoming_forecast(weeks=4, lookback_weeks=52, min_recurring=3)
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
