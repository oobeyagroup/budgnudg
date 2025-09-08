# transactions/reporting/pivot.py
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional
from django.db.models import Sum, F, Q, Value, DecimalField
from django.db.models.functions import TruncMonth
from transactions.models import Transaction
from django.utils.decorators import method_decorator
from transactions.utils import trace

@dataclass(frozen=True)
class MonthlyPivotSpec:
    dimension_expr: str          # e.g. "payoree__name"
    metric_expr: str = "amount"  # what to sum
    filters: Optional[Q] = None  # Q(...) extra filters
    start: Optional[date] = None
    end: Optional[date] = None
    include_zero_rows: bool = False

class MonthlyPivot:
    """Builds: {dimension: {YYYY-MM: Decimal, ...}, ...} and a sorted list of months."""

    @method_decorator(trace)
    def __init__(self, spec: MonthlyPivotSpec):
        self.spec = spec

    @method_decorator(trace)
    def months_range(self, qs) -> list[date]:
        qs = qs.annotate(m=TruncMonth("date")).values("m").order_by("m").distinct()
        if self.spec.start: qs = qs.filter(date__gte=self.spec.start)
        if self.spec.end: qs = qs.filter(date__lt=self.spec.end)
        return [row["m"] for row in qs]

    @method_decorator(trace)
    def run(self) -> tuple[list[date], list[dict]]:
        qs = Transaction.objects.all()
        if self.spec.filters:
            qs = qs.filter(self.spec.filters)
        if self.spec.start:
            qs = qs.filter(date__gte=self.spec.start)
        if self.spec.end:
            qs = qs.filter(date__lt=self.spec.end)

        months = self.months_range(qs)
        # Aggregate per (dimension, month)
        agg = (
            qs.annotate(month=TruncMonth("date"))
              .values(self.spec.dimension_expr, "month")
              .annotate(total=Sum(self.spec.metric_expr))
              .order_by(self.spec.dimension_expr, "month")
        )

        # Pivot in Python to keep SQL simple
        table = {}
        for row in agg:
            key = row[self.spec.dimension_expr]
            m = row["month"]
            table.setdefault(key, {})[m] = row["total"]

        # Optionally include rows with zeros for months not present
        rows = []
        for key, mdata in table.items():
            rows.append({
                "dimension": key,
                **{m: mdata.get(m) or 0 for m in months},
                "total": sum((mdata.get(m) or 0) for m in months),
            })

        rows.sort(key=lambda r: r["total"], reverse=True)
        return months, rows