import datetime as dt
from django.test import TestCase
from transactions.selectors import build_upcoming_forecast
from transactions.models import Transaction, Category


class UpcomingForecastTests(TestCase):
    def test_build_upcoming_forecast_basic(self):
        # create some historical weekly transactions
        cat, _ = Category.objects.get_or_create(name="Test")
        today = dt.date.today()
        for w in range(1, 13):
            d = today - dt.timedelta(weeks=w)
            Transaction.objects.create(
                date=d, amount=100 + w, description=f"Sample {w}", category=cat
            )

        result = build_upcoming_forecast(weeks=4)
        assert "week_starts" in result
        assert len(result["week_starts"]) == 4
        assert len(result["projected_weekly_totals"]) == 4

    def test_recurring_detection(self):
        cat, _ = Category.objects.get_or_create(name="Bills")
        today = dt.date.today()
        # create a recurring weekly transaction with similar description
        # Start from 5 days ago so the next prediction falls in the upcoming window
        for i in range(6):
            d = today - dt.timedelta(days=i * 7 + 5)
            Transaction.objects.create(
                date=d, amount=-50, description="ACME SUBSCRIPTION 123", category=cat
            )

        result = build_upcoming_forecast(weeks=4)
        # Filter for our test transaction specifically
        test_predictions = [
            p
            for p in result.get("recurring_predictions", [])
            if "ACME SUBSCRIPTION" in p.get("description", "")
        ]
        # at least one recurring prediction for our test data should be present
        assert len(test_predictions) >= 1

    def test_build_upcoming_forecast_basic(self):
        # create some historical weekly transactions
        cat, _ = Category.objects.get_or_create(name="Test")
        today = dt.date.today()
        for w in range(1, 13):
            d = today - dt.timedelta(weeks=w)
            Transaction.objects.create(
                date=d, amount=100 + w, description=f"Sample {w}", category=cat
            )

        result = build_upcoming_forecast(weeks=4)
        assert "week_starts" in result
        assert len(result["week_starts"]) == 4
        assert len(result["projected_weekly_totals"]) == 4

    def test_recurring_detection(self):
        cat, _ = Category.objects.get_or_create(name="Bills")
        today = dt.date.today()
        # create a recurring weekly transaction with similar description
        # Start from 1 week ago so the next prediction falls in the upcoming window
        for i in range(6):
            d = today - dt.timedelta(weeks=i + 1)
            Transaction.objects.create(
                date=d, amount=-50, description="ACME SUBSCRIPTION 123", category=cat
            )

        result = build_upcoming_forecast(weeks=4)
        # Filter for our test transaction specifically
        test_predictions = [
            p
            for p in result.get("recurring_predictions", [])
            if "ACME SUBSCRIPTION" in p.get("description", "")
        ]
        # at least one recurring prediction for our test data should be present
        assert len(test_predictions) >= 1
