# transactions/reporting/nested_pivot.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from calendar import monthrange
from typing import Iterable
from decimal import Decimal
from django.db.models import Sum, Case, When, DecimalField, F, Q, Value
from transactions.models import Transaction
from django.utils.decorators import method_decorator
from transactions.utils import trace


@dataclass
class NestedPivotSpec:
    dims: list[
        str
    ]  # e.g. ["subcategory__parent__type", "subcategory__parent__name", "subcategory__name"]
    metric_expr: str = "amount"  # field/expression to sum
    filters: Q | None = None
    start: date | None = None
    end: date | None = None
    extras: list[str] | None = (
        None  # extra values to include at leaf (e.g. ["subcategory__id"])
    )


@trace
def _month_edges(start: date, end: date) -> list[tuple[date, date, str]]:
    """[(first_day, last_day_inclusive, 'YYYY-MM')]"""
    months: list[tuple[date, date, str]] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        last = monthrange(y, m)[1]
        months.append((date(y, m, 1), date(y, m, last), f"{y:04d}-{m:02d}"))
        m += 1
        if m == 13:
            m = 1
            y += 1
    return months


@trace
def nested_budget_data(spec: NestedPivotSpec) -> dict:
    assert spec.start and spec.end, "start/end required"
    qs = Transaction.objects.all()
    if spec.filters:
        qs = qs.filter(spec.filters)

    months = _month_edges(spec.start, spec.end)

    # Build conditional month sums as annotations
    month_annos: dict[str, Sum] = {
        label: Sum(
            Case(
                When(date__gte=first, date__lte=last, then=F(spec.metric_expr)),
                default=Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        for (first, last, label) in months
    }

    values_fields = list(spec.dims)
    if spec.extras:
        values_fields += spec.extras

    row_dicts = qs.values(*values_fields).annotate(**month_annos).order_by(*spec.dims)

    # Build a nested tree keyed by dims; at leaves attach:
    #   "__cells__": [month totals in same order as months]
    #   "__extra__": {extra_name: value, ...}
    #   "__is_intermediate__": True for intermediate nodes with calculated totals
    root: dict = {}
    labels = [label for *_, label in months]

    for row in row_dicts:
        cursor = root
        path = []  # Track path for calculating parent totals

        for dim in spec.dims:
            key = row[dim]
            if key is None:
                key = "Uncategorized"  # Handle None values
            path.append(key)
            cursor = cursor.setdefault(key, {})

        # Leaf node data
        cells = [row[label] for label in labels]
        leaf = cursor
        leaf["__cells__"] = cells
        if spec.extras:
            leaf["__extra__"] = {name: row[name] for name in spec.extras}

        # Calculate totals up the hierarchy
        _calculate_parent_totals(root, path, cells, labels)

    return {"tree": root, "months": labels}


def _calculate_parent_totals(root: dict, path: list, cells: list, labels: list):
    """Recursively calculate totals for parent nodes."""
    if not path:
        return

    current = root
    # Only add to parent levels, not all ancestors
    for i, key in enumerate(path[:-1]):  # Exclude the last element (leaf node)
        if key not in current:
            current[key] = {}

        current = current[key]

        # Initialize or update totals for this level
        if "__cells__" not in current:
            current["__cells__"] = [Decimal("0")] * len(labels)

        # Add leaf values to this parent level
        for j, value in enumerate(cells):
            if value is not None:
                current["__cells__"][j] += Decimal(str(value))

        # Mark as intermediate node
        current["__is_intermediate__"] = True
