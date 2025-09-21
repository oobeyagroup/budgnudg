# MonthlyPivot Utility – Developer Notes

We have a reusable MonthlyPivot helper that makes it easy to generate “pivot-table style” reports (rows × months) from the Transaction model. It centralizes the logic for:
- Filtering transactions (e.g. expenses only, or a single bank account).
- Grouping by any Django ORM expression (e.g. category, payee, account).
- Summing amounts per month.
- Rendering a standard month-by-month table using a shared template partial.

## Anatomy

A pivot report has two pieces:
1.	Spec (MonthlyPivotSpec)
    - Defines the dimension (what goes in the rows),
    - the metric (what to sum),
    - optional filters, and
    - a start/end date range.
2.	Runner (MonthlyPivot)
    - Given a spec, runs the query and produces two objects:
    - months: a list of datetime objects (first of each month).
    - rows: a list of dicts with keys:
    - "dimension" (row label)
    - <month_date> (amount for that month)
    - "total" (row total across months)

## Usage Example

A Budget by Category report:
```
# views/reports.py
from datetime import date
from django.views.generic import TemplateView
from django.db.models import Q
from transactions.reporting.pivot import MonthlyPivot, MonthlyPivotSpec

class BudgetMonthlyReport(TemplateView):
    template_name = "transactions/report_budget.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        spec = MonthlyPivotSpec(
            dimension_expr="subcategory__parent__name",  # group by parent category
            metric_expr="amount",                        # sum this field
            filters=Q(amount__lt=0),                     # expenses only
            start=date(date.today().year, 1, 1),         # current year
        )
        months, rows = MonthlyPivot(spec).run()

        ctx.update({
            "months": months,
            "rows": rows,
            "heading": "Category",
            "title": "Budget (Monthly, by Category)",
        })
        return ctx
 ```   

## Rendering

All reports share the same partial:
{% include "partials/monthly_pivot_table.html" with heading=heading months=months rows=rows %}

This outputs a standard <table> with:
- A header row for months.
- One row per dimension value.
- A “Total” column at the end.


## Creating New Reports

To add a new monthly pivot report:
1.	Define a View
- Subclass TemplateView.
- Build a MonthlyPivotSpec with your grouping/filtering.
- Call MonthlyPivot(spec).run() and put months + rows in context.
2.	Add URL Pattern
- Point to your new view.
3.	Add Template
- Extend base.html.
- Include the shared pivot partial with an appropriate heading.

That’s it. The only thing that varies between reports is the spec (dimension_expr, filters, title).


Monthly Pivot – Spec Catalog

Import once:
```
from datetime import date
from django.db.models import Q
from transactions.reporting.pivot import MonthlyPivotSpec
```

1) Expenses by Category (Parent)

Group all expenses by parent category.

```
spec = MonthlyPivotSpec(
    dimension_expr="subcategory__parent__name",
    metric_expr="amount",
    filters=Q(amount__lt=0),
    start=date(date.today().year, 1, 1),
)
```
Notes: Good top-level budget view. Add end= for a shorter range if needed.

2) Expenses by Subcategory

Drill into subcategories.
spec = MonthlyPivotSpec(
    dimension_expr="subcategory__name",
    metric_expr="amount",
    filters=Q(amount__lt=0),
    start=date(date.today().year, 1, 1),
)

3) Income by Category

Only income categories (assuming income is amount__gt=0).
```
spec = MonthlyPivotSpec(
    dimension_expr="subcategory__parent__name",
    metric_expr="amount",
    filters=Q(amount__gt=0),
    start=date(date.today().year, 1, 1),
)
```
4) Net by Category (Income – Expense)

No sign filter; sums both.
```
spec = MonthlyPivotSpec(
    dimension_expr="subcategory__parent__name",
    metric_expr="amount",
    start=date(date.today().year, 1, 1),
)
```
5) Expenses by Payee

Who you pay most.
```
spec = MonthlyPivotSpec(
    dimension_expr="payoree__name",
    metric_expr="amount",
    filters=Q(amount__lt=0),
    start=date(date.today().year, 1, 1),
)
```

6) Income by Payee

Who pays you.
```
spec = MonthlyPivotSpec(
    dimension_expr="payoree__name",
    metric_expr="amount",
    filters=Q(amount__gt=0),
    start=date(date.today().year, 1, 1),
)
```

7) Expenses by Bank Account

Per-account outflows.
```
spec = MonthlyPivotSpec(
    dimension_expr="bank_account",
    metric_expr="amount",
    filters=Q(amount__lt=0),
    start=date(date.today().year, 1, 1),
)
```

8) Specific Account: Category Breakdown

Add a fixed filter for one account.
```
target_acct = "CHK-3607"
spec = MonthlyPivotSpec(
    dimension_expr="subcategory__parent__name",
    metric_expr="amount",
    filters=Q(amount__lt=0, bank_account=target_acct),
    start=date(date.today().year, 1, 1),
)
```

9) “Needs vs Wants” (if you store a flag)

Assuming subcategory__parent__type or similar (adjust to your field).
```
spec = MonthlyPivotSpec(
    dimension_expr="subcategory__parent__type",  # e.g., "need" / "want"
    metric_expr="amount",
    filters=Q(amount__lt=0),
    start=date(date.today().year, 1, 1),
)
```

10) Tags (if using many-to-many Tag)

If your Transaction has tags M2M; use annotation or a flat name via .values('tags__name').
```
spec = MonthlyPivotSpec(
    dimension_expr="tags__name",
    metric_expr="amount",
    filters=Q(amount__lt=0),
    start=date(date.today().year, 1, 1),
)
```
Tip: You may want to prefilter to a subset of tags with filters=Q(tags__name__in=[...]).

11) Recurring Merchant Watchlist

Focus on a few merchants/payees you care about.

```
watch = ["NETFLIX", "SPOTIFY", "ELECTRIC CO"]
spec = MonthlyPivotSpec(
    dimension_expr="payoree__name",
    metric_expr="amount",
    filters=Q(amount__lt=0, payoree__name__in=watch),
    start=date(date.today().year, 1, 1),
)
```

12) Custom Keyword Bucket (Ad-hoc)

Bucket by a keyword present in description (quick & dirty).

```
kw = "GROCERY"
spec = MonthlyPivotSpec(
    dimension_expr="subcategory__parent__name",  # or "payoree__name"
    metric_expr="amount",
    filters=Q(amount__lt=0, description__icontains=kw),
    start=date(date.today().year, 1, 1),
)
```
Tips & Patterns
	•	Date Window: Add end=date(YYYY, MM, 1) to cap the range.
	•	Sign Conventions: If expenses are negative, use amount__lt=0; income positive with amount__gt=0.
	•	Display Labels: If dimension_expr can be NULL, the pivot will label it “(Uncategorized)” (implementation detail—adjust in the helper if you want a different label).
	•	Top-N: If a dimension explodes (e.g., many payees), filter first:
    ```
    filters = Q(amount__lt=0, payoree__name__in=top_payees_list)
    ```

(Compute top_payees_list via an aggregation query beforehand.)

	•	Reuse: Put common specs in transactions/reporting/specs.py and import them in views.
