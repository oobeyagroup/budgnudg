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


def recent_transactions(limit=50):
    return Transaction.objects.order_by("-date")[:limit]


def account_summary():
    # build your per-account monthly counts + missing subcategory/payoree counts
    ...


CHECK_RE = re.compile(r"\bCHECK\s*(\d{3,6})\b", re.IGNORECASE)


def extract_check_number_from_description(desc: str) -> int | None:
    if not desc:
        return None
    m = CHECK_RE.search(desc)
    return int(m.group(1)) if m else None


def check_like_transactions(account: str | None = None, start=None, end=None):
    qs = Transaction.objects.filter(description__iregex=r"\bCHECK\s*\d+")
    if account:
        qs = qs.filter(bank_account=account)
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lte=end)
    return qs.select_related("payoree", "subcategory").order_by("-date")


def build_upcoming_forecast(
    weeks: int = 4, lookback_weeks: int = 52, min_recurring: int = 3
):
    """Build a simple upcoming forecast for the next `weeks` weeks.

    Strategy:
    - Pull transactions from the last `lookback_weeks` weeks.
    - Aggregate weekly totals and use recent-week moving average (default: last 12 weeks)
      to project total inflows/outflows for each upcoming week.
    - Detect recurring transactions by grouping on a normalized description/pattern
      and looking for regular intervals (weekly/biweekly/monthly). Project their
      next occurrences into the forecast window.

    Returns a dict with:
    {
      "week_starts": [date,...],
      "projected_weekly_totals": [Decimal,...],
      "weekly_details": {week_start: {"by_category": {...}, "recurring": [...] }},
      "recurring_predictions": [ {"description":..., "amount":..., "next_date":..., "freq_days":...}, ... ]
    }
    """
    # time window
    today = dt.date.today()

    # determine week starts (Mon) for upcoming weeks
    def week_start(d):
        return d - dt.timedelta(days=d.weekday())

    upcoming_week_starts = [
        week_start(today) + dt.timedelta(weeks=i) for i in range(1, weeks + 1)
    ]

    lookback_start = week_start(today) - dt.timedelta(weeks=lookback_weeks)

    qs = (
        Transaction.objects.filter(date__gte=lookback_start)
        .select_related("category", "payoree")
        .order_by("date")
    )

    # aggregate transactions by week_start
    weekly_sums = {}
    weekly_incomes = {}
    weekly_expenses = {}
    weekly_by_category = {}
    all_transactions = list(qs)
    for t in all_transactions:
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

    # Use recent 12 weeks for moving average if available
    recent_weeks = sorted(
        [d for d in weekly_sums.keys() if d <= week_start(today)], reverse=True
    )[:12]
    recent_net = [weekly_sums[d] for d in recent_weeks] if recent_weeks else [0]
    recent_incomes = (
        [weekly_incomes.get(d, 0) for d in recent_weeks] if recent_weeks else [0]
    )
    recent_expenses = (
        [weekly_expenses.get(d, 0) for d in recent_weeks] if recent_weeks else [0]
    )
    avg_net = statistics.mean(recent_net) if recent_net else 0
    avg_income = statistics.mean(recent_incomes) if recent_incomes else 0
    avg_expense = statistics.mean(recent_expenses) if recent_expenses else 0

    # Project each upcoming week using the averages (we'll convert to daily below)
    projected_weekly_totals = [avg_net for _ in upcoming_week_starts]
    projected_weekly_incomes = [avg_income for _ in upcoming_week_starts]
    projected_weekly_expenses = [avg_expense for _ in upcoming_week_starts]

    # Get payoree IDs for designated series logic
    payoree_ids = {t.payoree.id for t in all_transactions if t.payoree}

    # Recurring detection: group by payoree
    def normalize_desc(s: str) -> str:
        if not s:
            return ""
        s2 = s.lower()
        # remove numbers and punctuation that commonly vary
        s2 = re.sub(r"\d+", "", s2)
        s2 = re.sub(r"[^a-z\s]", "", s2)
        s2 = re.sub(r"\s+", " ", s2).strip()
        return s2

    groups = {}
    for t in all_transactions:
        # Use payoree name as the grouping key, fallback to normalized description if no payoree
        if t.payoree:
            key = t.payoree.name.lower().strip()
        else:
            # Fallback to normalized description for transactions without payoree
            key = normalize_desc(t.description)
        if not key:
            continue
        groups.setdefault(key, []).append(t)

    # Get payoree IDs that have designated series to exclude from recurring detection
    designated_payoree_ids = set()
    if payoree_ids:
        designated_series = RecurringSeries.objects.filter(
            payoree_id__in=payoree_ids,
            active=True
        )
        designated_payoree_ids = {s.payoree_id for s in designated_series}

    recurring_predictions = []
    for key, txns in groups.items():
        if len(txns) < min_recurring:
            continue
            
        # Skip if this is a payoree that already has a designated series
        first_txn = txns[0]
        if first_txn.payoree and first_txn.payoree.id in designated_payoree_ids:
            continue
        dates = sorted([t.date for t in txns])
        deltas = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
        if not deltas:
            continue
        median_delta = int(statistics.median(deltas))
        # classify reasonable intervals
        if 5 <= median_delta <= 10:
            freq_days = 7
        elif 11 <= median_delta <= 18:
            freq_days = 14
        elif 20 <= median_delta <= 40:
            freq_days = 30
        else:
            # skip very irregular patterns
            continue

        last_tx = max(txns, key=lambda x: x.date)
        next_date = last_tx.date + dt.timedelta(days=freq_days)
        # include predictions falling into upcoming window
        if (
            week_start(today)
            <= next_date
            <= week_start(today) + dt.timedelta(weeks=weeks)
        ):
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

    # Find designated recurring series (existing RecurringSeries that match our transactions)
    designated_recurring = []
    if payoree_ids:
        # Look for active RecurringSeries that match payorees in our transaction set
        designated_series = RecurringSeries.objects.filter(
            payoree_id__in=payoree_ids,
            active=True
        ).select_related('payoree')
        
        for series in designated_series:
            # Calculate next due date based on interval
            if series.interval == "weekly":
                freq_days = 7
            elif series.interval == "biweekly":
                freq_days = 14
            elif series.interval == "monthly":
                freq_days = 30
            else:
                continue
                
            # Use last_seen, or first_seen, or the most recent transaction date for this payoree
            if series.last_seen:
                reference_date = series.last_seen
            elif series.first_seen:
                reference_date = series.first_seen
            else:
                # Find the most recent transaction for this payoree
                recent_txn = Transaction.objects.filter(
                    payoree=series.payoree
                ).order_by('-date').first()
                reference_date = recent_txn.date if recent_txn else today
            
            next_date = reference_date + dt.timedelta(days=freq_days)
            
            # Include if it falls in upcoming window
            if (
                week_start(today)
                <= next_date
                <= week_start(today) + dt.timedelta(weeks=weeks)
            ):
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

    # Convert weekly averages to daily averages for the forecast window
    avg_daily_income = avg_income / 7.0
    avg_daily_expense = avg_expense / 7.0

    # build list of upcoming days (next N days)
    total_days = weeks * 7
    upcoming_days = [today + dt.timedelta(days=i) for i in range(1, total_days + 1)]

    # initialize daily projections with the daily averages
    daily_income = {d: avg_daily_income for d in upcoming_days}
    daily_expense = {d: avg_daily_expense for d in upcoming_days}
    daily_transactions = {d: [] for d in upcoming_days}

    # Allow for user-designated recurring series (if a RecurringSeries model exists).
    # We'll treat detected recurrences as "suggestions" and avoid injecting any
    # occurrences that match a designated series. This keeps the automatic
    # detector as a recommendation layer while letting user-managed recurrences
    # drive the canonical schedule.
    designated_recurring = []
    
    # Build a list of designated series with payoree name,
    # amount cents and tolerance so we can match by amount within tolerance.
    designated_series = []
    for s in RecurringSeries.objects.filter(active=True):
        pay_name = None
        if hasattr(s, "payoree") and getattr(s, "payoree"):
            try:
                pay_name = s.payoree.name
            except Exception:
                pass
        designated_series.append(
            {
                "pay": pay_name,
                "amount_cents": getattr(s, "amount_cents", None),
                "tolerance": getattr(s, "amount_tolerance_cents", 0),
            }
        )

    # split detected predictions into designated (user-managed) and suggested
    suggested_predictions = []
    remaining_designated = []
    def _amount_cents_from_amount(a):
        try:
            return int(round(abs(float(a)) * 100))
        except Exception:
            return None

    for p in recurring_predictions:
        pd = normalize_desc(p.get("description", "") or "")
        pay = p.get("payoree")
        amount_cents_p = _amount_cents_from_amount(p.get("amount", 0))

        matched = False
        for s in designated_series:
            pay_match = pay and s.get("pay") and pay == s.get("pay")
            if not pay_match:
                continue

            # If we have amount information, apply tolerance matching.
            s_amount = s.get("amount_cents")
            s_tol = s.get("tolerance") or 0
            if s_amount is None or amount_cents_p is None:
                # fallback to merchant/payee match only
                matched = True
                break

            if abs(amount_cents_p - s_amount) <= s_tol:
                matched = True
                break

        if matched:
            remaining_designated.append(p)
        else:
            suggested_predictions.append(p)

    # Put only suggested predicted transactions into the daily buckets and adjust subtotals
    for p in suggested_predictions:
        nd = p.get("next_date")
        if nd and nd in daily_transactions:
            # transaction dict: date, amount, description, payoree
            tx = {
                "date": nd,
                "amount": p.get("amount", 0),
                "description": p.get("description"),
                "payoree": p.get("payoree"),
                "freq_days": p.get("freq_days"),
            }
            daily_transactions[nd].append(tx)
            # adjust daily income/expense totals
            amt = float(p.get("amount", 0))
            if amt >= 0:
                daily_income[nd] = daily_income.get(nd, 0) + amt
            else:
                daily_expense[nd] = daily_expense.get(nd, 0) + abs(amt)

    # compute per-day net and window subtotals
    daily_net = {d: daily_income[d] - daily_expense[d] for d in upcoming_days}
    total_income = sum(daily_income.values())
    total_expense = sum(daily_expense.values())
    total_net = total_income - total_expense

    # return daily-oriented forecast
    result = {
        "days": upcoming_days,
        "daily_income": [daily_income[d] for d in upcoming_days],
        "daily_expense": [daily_expense[d] for d in upcoming_days],
        "daily_net": [daily_net[d] for d in upcoming_days],
        "daily_transactions": daily_transactions,
        "totals": {"income": total_income, "expense": total_expense, "net": total_net},
        "recurring_predictions": suggested_predictions,
        "designated_recurring": designated_recurring,
    }

    # Backwards compatibility: tests and callers expect weekly-oriented keys
    try:
        result["week_starts"] = upcoming_week_starts
        result["projected_weekly_totals"] = projected_weekly_totals
        result["weekly_details"] = weekly_by_category
    except Exception:
        # If any of these are missing for some reason, skip silently
        pass

    return result
