# transactions/selectors.py
from django.db.models import (
    Count,
    Q,
    F,
)  # Q = complex logical conditions; F = refer to fields in expressions, not just static values.
from transactions.models import Transaction, Category
from transactions.models import RecurringSeries
import re
import datetime as dt
import statistics
import logging
from transactions.utils import trace
from typing import List, Dict, Any, Optional, Tuple, Set

logger = logging.getLogger(__name__)


def recent_transactions(limit=50):
    return Transaction.objects.order_by("-date")[:limit]


def account_summary():
    # build your per-account monthly counts + missing subcategory/payoree counts
    ...


CHECK_RE = re.compile(r"\bCHECK\s*(\d{3,6})\b", re.IGNORECASE)


@trace
def extract_check_number_from_description(desc: str) -> int | None:
    if not desc:
        return None
    m = CHECK_RE.search(desc)
    return int(m.group(1)) if m else None


@trace
def check_like_transactions(account: str | None = None, start=None, end=None):
    qs = Transaction.objects.filter(description__iregex=r"\bCHECK\s*\d+")
    if account:
        qs = qs.filter(bank_account=account)
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lte=end)
    return qs.select_related("payoree", "subcategory").order_by("-date")


def get_upcoming_week_starts(weeks: int, today: dt.date) -> List[dt.date]:
    """Calculate the start dates (Mondays) for upcoming weeks."""

    def week_start(d: dt.date) -> dt.date:
        return d - dt.timedelta(days=d.weekday())

    return [week_start(today) + dt.timedelta(weeks=i) for i in range(1, weeks + 1)]


def aggregate_transactions_by_week(
    transactions: List[Transaction], lookback_start: dt.date
) -> Dict[str, Any]:
    """Aggregate transaction data by week start date."""

    def week_start(d: dt.date) -> dt.date:
        return d - dt.timedelta(days=d.weekday())

    weekly_sums: Dict[dt.date, float] = {}
    weekly_incomes: Dict[dt.date, float] = {}
    weekly_expenses: Dict[dt.date, float] = {}
    weekly_by_category: Dict[dt.date, Dict[str, float]] = {}

    for t in transactions:
        ws = week_start(t.date)
        weekly_sums.setdefault(ws, 0)
        weekly_incomes.setdefault(ws, 0)
        weekly_expenses.setdefault(ws, 0)

        amt = float(t.amount)
        weekly_sums[ws] += amt

        if amt >= 0:
            weekly_incomes[ws] += amt
        else:
            weekly_expenses[ws] += abs(amt)

        weekly_by_category.setdefault(ws, {})
        cat = t.category.name if t.category else "Uncategorized"
        weekly_by_category[ws].setdefault(cat, 0)
        weekly_by_category[ws][cat] += float(t.amount)

    return {
        "sums": weekly_sums,
        "incomes": weekly_incomes,
        "expenses": weekly_expenses,
        "by_category": weekly_by_category,
    }


def compute_moving_averages(
    weekly_data: Dict[str, Any], today: dt.date, weeks_for_avg: int = 12
) -> Dict[str, float]:
    """Compute moving averages from recent weekly data."""

    def week_start(d: dt.date) -> dt.date:
        return d - dt.timedelta(days=d.weekday())

    recent_weeks = sorted(
        [d for d in weekly_data["sums"].keys() if d <= week_start(today)], reverse=True
    )[:weeks_for_avg]

    if not recent_weeks:
        return {"net": 0, "income": 0, "expense": 0}

    recent_net = [weekly_data["sums"][d] for d in recent_weeks]
    recent_incomes = [weekly_data["incomes"].get(d, 0) for d in recent_weeks]
    recent_expenses = [weekly_data["expenses"].get(d, 0) for d in recent_weeks]

    return {
        "net": statistics.mean(recent_net),
        "income": statistics.mean(recent_incomes),
        "expense": statistics.mean(recent_expenses),
    }


def normalize_description(desc: str) -> str:
    """Normalize transaction descriptions for grouping."""
    if not desc:
        return ""
    s = desc.lower()
    s = re.sub(r"\d+", "", s)
    s = re.sub(r"[^a-z\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def detect_recurring_transactions(
    transactions: List[Transaction],
    min_recurring: int,
    designated_payoree_ids: Set[int],
) -> List[Dict[str, Any]]:
    """Detect recurring transaction patterns."""
    groups: Dict[str, List[Transaction]] = {}
    for t in transactions:
        if t.payoree:
            key = t.payoree.name.lower().strip()
        else:
            key = normalize_description(t.description)

        if not key:
            continue
        groups.setdefault(key, []).append(t)

    recurring_predictions: List[Dict[str, Any]] = []
    for key, txns in groups.items():
        if len(txns) < min_recurring:
            continue

        first_txn = txns[0]
        if first_txn.payoree and first_txn.payoree.id in designated_payoree_ids:  # type: ignore
            continue

        dates = sorted([t.date for t in txns])
        deltas = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]

        if not deltas:
            continue

        median_delta = int(statistics.median(deltas))

        if 5 <= median_delta <= 10:
            freq_days = 7
        elif 11 <= median_delta <= 18:
            freq_days = 14
        elif 20 <= median_delta <= 40:
            freq_days = 30
        else:
            continue

        last_tx = max(txns, key=lambda x: x.date)
        next_date = last_tx.date + dt.timedelta(days=freq_days)

        recurring_predictions.append(
            {
                "description": last_tx.description,
                "payoree": (last_tx.payoree.name if last_tx.payoree else None),
                "amount": float(last_tx.amount),
                "next_date": next_date,
                "freq_days": freq_days,
                "sample_count": len(txns),
            }
        )

    return recurring_predictions


def get_designated_recurring_series(
    payoree_ids: Set[int], weeks: int, today: dt.date
) -> List[Dict[str, Any]]:
    """Get designated recurring series for the forecast period."""

    def week_start(d: dt.date) -> dt.date:
        return d - dt.timedelta(days=d.weekday())

    if not payoree_ids:
        return []

    designated_series = RecurringSeries.objects.filter(
        payoree_id__in=payoree_ids, active=True
    ).select_related("payoree")

    designated_recurring: List[Dict[str, Any]] = []
    for series in designated_series:
        if series.interval == "weekly":
            freq_days = 7
        elif series.interval == "biweekly":
            freq_days = 14
        elif series.interval == "monthly":
            freq_days = 30
        else:
            continue

        # Use next_due if it's set and in the future, otherwise calculate from reference dates
        if series.next_due and series.next_due >= today:
            next_date = series.next_due
        else:
            if series.last_seen:
                reference_date = series.last_seen
            elif series.first_seen:
                reference_date = series.first_seen
            else:
                recent_txn = (
                    Transaction.objects.filter(payoree=series.payoree)
                    .order_by("-date")
                    .first()
                )
                reference_date = recent_txn.date if recent_txn else today

            next_date = reference_date + dt.timedelta(days=freq_days)

        if (
            week_start(today)
            <= next_date
            <= week_start(today) + dt.timedelta(weeks=weeks)
        ):
            if series.payoree:
                designated_recurring.append(
                    {
                        "description": f"{series.payoree.name} (Designated)",
                        "payoree": series.payoree.name,
                        "amount": float(series.amount_cents) / 100.0,
                        "next_date": next_date,
                        "freq_days": freq_days,
                        "series_id": series.id,
                        "confidence": series.confidence,
                    }
                )

    return designated_recurring


def match_predictions_to_designated(
    predictions: List[Dict[str, Any]], designated_series: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Match detected predictions to designated series."""

    def _amount_cents_from_amount(a: float) -> Optional[int]:
        try:
            return int(round(abs(float(a)) * 100))
        except Exception:
            return None

    suggested_predictions: List[Dict[str, Any]] = []
    remaining_designated: List[Dict[str, Any]] = []

    for p in predictions:
        pd = normalize_description(p.get("description", "") or "")
        pay = p.get("payoree")
        amount_cents_p = _amount_cents_from_amount(p.get("amount", 0))

        matched = False
        for s in designated_series:
            pay_match = pay and s.get("pay") and pay == s.get("pay")
            if not pay_match:
                continue

            s_amount = s.get("amount_cents")
            s_tol = s.get("tolerance") or 0
            if s_amount is None or amount_cents_p is None:
                matched = True
                break

            if abs(amount_cents_p - s_amount) <= s_tol:
                matched = True
                break

        if matched:
            remaining_designated.append(p)
        else:
            suggested_predictions.append(p)

    return suggested_predictions, remaining_designated


def build_daily_projections(
    upcoming_days: List[dt.date],
    avg_daily_income: float,
    avg_daily_expense: float,
    predictions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build daily projections with recurring transactions."""
    daily_income: Dict[dt.date, float] = {d: avg_daily_income for d in upcoming_days}
    daily_expense: Dict[dt.date, float] = {d: avg_daily_expense for d in upcoming_days}
    daily_transactions: Dict[dt.date, List[Dict[str, Any]]] = {
        d: [] for d in upcoming_days
    }

    for p in predictions:
        nd = p.get("next_date")
        if nd and nd in daily_transactions:
            tx: Dict[str, Any] = {
                "date": nd,
                "amount": p.get("amount", 0),
                "description": p.get("description"),
                "payoree": p.get("payoree"),
                "freq_days": p.get("freq_days"),
            }
            daily_transactions[nd].append(tx)

            amt = float(p.get("amount", 0))
            if amt >= 0:
                daily_income[nd] += amt
            else:
                daily_expense[nd] += abs(amt)

    daily_net = {d: daily_income[d] - daily_expense[d] for d in upcoming_days}
    total_income = sum(daily_income.values())
    total_expense = sum(daily_expense.values())
    total_net = total_income - total_expense

    return {
        "daily_income": [daily_income[d] for d in upcoming_days],
        "daily_expense": [daily_expense[d] for d in upcoming_days],
        "daily_net": [daily_net[d] for d in upcoming_days],
        "daily_transactions": daily_transactions,
        "totals": {"income": total_income, "expense": total_expense, "net": total_net},
    }


@trace
def build_upcoming_forecast(
    weeks: int = 4, lookback_weeks: int = 52, min_recurring: int = 3
):
    """Build a simple upcoming forecast for the next `weeks` weeks."""
    today = dt.date.today()

    # Get time windows
    upcoming_week_starts = get_upcoming_week_starts(weeks, today)
    lookback_start = upcoming_week_starts[0] - dt.timedelta(weeks=lookback_weeks)

    # Get transactions
    qs = (
        Transaction.objects.filter(date__gte=lookback_start)
        .select_related("category", "payoree")
        .order_by("date")
    )
    all_transactions = list(qs)

    # Aggregate weekly data
    weekly_data = aggregate_transactions_by_week(all_transactions, lookback_start)

    # Compute moving averages
    averages = compute_moving_averages(weekly_data, today)

    # Get payoree IDs for designated series logic
    payoree_ids: Set[int] = {t.payoree.id for t in all_transactions if t.payoree}  # type: ignore

    # Get designated payoree IDs to exclude from detection
    designated_payoree_ids: Set[int] = set()
    if payoree_ids:
        designated_series = RecurringSeries.objects.filter(
            payoree_id__in=payoree_ids, active=True
        )
        designated_payoree_ids = {s.payoree_id for s in designated_series}  # type: ignore

    # Detect recurring transactions
    recurring_predictions = detect_recurring_transactions(
        all_transactions, min_recurring, designated_payoree_ids
    )

    # Get designated recurring series
    designated_recurring = get_designated_recurring_series(payoree_ids, weeks, today)

    # Build designated series list for matching
    designated_series_list: List[Dict[str, Any]] = []
    for s in RecurringSeries.objects.filter(active=True):
        pay_name = None
        if hasattr(s, "payoree") and getattr(s, "payoree"):
            try:
                pay_name = s.payoree.name  # type: ignore
            except Exception:
                pass
        designated_series_list.append(
            {
                "pay": pay_name,
                "amount_cents": getattr(s, "amount_cents", None),
                "tolerance": getattr(s, "amount_tolerance_cents", 0),
            }
        )

    # Match predictions to designated series
    suggested_predictions, _ = match_predictions_to_designated(
        recurring_predictions, designated_series_list
    )

    # Combine suggested predictions with designated recurring series
    all_predictions = suggested_predictions + designated_recurring

    # Build daily projections
    upcoming_days = [today + dt.timedelta(days=i) for i in range(1, weeks * 7 + 1)]
    avg_daily_income = averages["income"] / 7.0
    avg_daily_expense = averages["expense"] / 7.0

    daily_data = build_daily_projections(
        upcoming_days, avg_daily_income, avg_daily_expense, all_predictions
    )

    # Build result
    result: Dict[str, Any] = {
        "days": upcoming_days,
        **daily_data,
        "recurring_predictions": suggested_predictions,
        "designated_recurring": designated_recurring,
    }

    # Backwards compatibility
    try:
        result["week_starts"] = upcoming_week_starts
        result["projected_weekly_totals"] = [averages["net"]] * len(
            upcoming_week_starts
        )
        result["weekly_details"] = weekly_data["by_category"]
    except Exception:
        pass

    return result
