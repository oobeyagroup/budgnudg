# transactions/views/report_budget.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.shortcuts import render, get_object_or_404
from django.views import View
from django.db.models import Sum
from django.db.models.functions import ExtractMonth

# Your nested pivot utilities (assumed from our earlier work)
from transactions.reporting.nested_pivot import NestedPivotSpec, nested_budget_data
from transactions.models import Category, Transaction


def _safe_sum(values: list[Any] | None) -> Decimal:
    if not values:
        return Decimal("0")
    total = Decimal("0")
    for v in values:
        if v is None:
            continue
        # let Decimal, int, float work
        total += Decimal(str(v))
    return total


def _annotate_totals(node: dict) -> None:
    """
    Recursively add:
      - node["row_total"]: sum of this node's own monthly cells
      - node["children_total"]: sum of child totals
      - node["total"]: row_total + children_total
    """
    cells = node.get("cells") or []
    node["row_total"] = _safe_sum(cells)

    children = node.get("children") or []
    for child in children:
        _annotate_totals(child)

    node["children_total"] = _safe_sum([c.get("total", 0) for c in children])
    node["total"] = node["row_total"] + node["children_total"]


class BudgetNestedReportView(View):
    template_name = "transactions/report_budget_nested.html"

    def get(self, request):
        year = int(request.GET.get("year", date.today().year))

        # Define the nested pivot spec (3-level budget: Type → Category → Subcategory)
        spec = NestedPivotSpec(
            dims=[
                "subcategory__parent__type",  # e.g., Needs / Wants / Savings / Income
                "subcategory__parent__name",  # parent Category name
                "subcategory__name",  # Subcategory name
            ],
            metric_expr="amount",
            # You can choose the date window helper you implemented in nested_pivot
            start=date(year, 1, 1),
            end=date(year + 1, 1, 1),
        )

        # Returns {"tree": nested_dict, "months": [labels]}
        data = nested_budget_data(spec)
        tree = data["tree"]
        month_labels = data["months"]

        # Convert tree to list format expected by template
        nodes = self._tree_to_nodes(tree)

        # Compute totals on every node
        for n in nodes:
            _annotate_totals(n)

        # Grand total across top-level nodes
        grand_total = _safe_sum([n.get("total", 0) for n in nodes])

        context = {
            "year": year,
            "nodes": nodes,
            "grand_total": grand_total,
            "month_labels": month_labels,
        }
        return render(request, self.template_name, context)

    def _tree_to_nodes(self, tree: dict, level: int = 0) -> list[dict]:
        """Convert nested tree dict to list of nodes for template."""
        nodes = []
        for key, value in tree.items():
            if key is None:
                continue  # Skip None keys
            if isinstance(value, dict):
                if "__cells__" in value:
                    # This is a leaf node
                    node = {
                        "label": str(key),
                        "cells": value["__cells__"],
                        "children": [],
                        "level": level,
                    }
                    if "__extra__" in value:
                        node["extra"] = value["__extra__"]
                    nodes.append(node)
                else:
                    # This is an intermediate node
                    children = self._tree_to_nodes(value, level + 1)
                    node = {
                        "label": str(key),
                        "cells": [],  # Intermediate nodes don't have their own cells
                        "children": children,
                        "level": level,
                    }
                    nodes.append(node)
        return nodes


class BudgetDrilldownView(View):
    """
    Breaks down a single SubCategory by month with a transactions table.
    URL: /transactions/reports/budget/subcat/<int:subcat_id>/?year=YYYY
    """

    template_name = "transactions/report_budget_drilldown.html"

    def get(self, request, *args, **kwargs):
        subcat_id = kwargs.get("subcat_id")
        if not subcat_id:
            # Handle case where no subcat_id is provided
            return render(
                request, self.template_name, {"error": "No subcategory specified"}
            )

        year = int(request.GET.get("year", date.today().year))
        subcat = get_object_or_404(
            Category.objects.select_related("parent"),
            pk=subcat_id,
        )

        qs = Transaction.objects.filter(
            subcategory_id=subcat.id, date__year=year
        ).annotate(month=ExtractMonth("date"))

        # Monthly totals 1..12
        monthly = {m: Decimal("0") for m in range(1, 13)}
        for row in qs.values("month").order_by("month").annotate(total=Sum("amount")):
            m = row["month"]
            if m:
                monthly[m] = monthly.get(m, Decimal("0")) + (
                    row["total"] or Decimal("0")
                )

        month_labels = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]
        month_values = [monthly[i] for i in range(1, 13)]
        grand_total = sum(month_values, Decimal("0"))

        # Transactions list (you can paginate later)
        txns = (
            Transaction.objects.filter(subcategory_id=subcat.id, date__year=year)
            .select_related("subcategory", "subcategory__parent", "payoree")
            .order_by("-date", "-id")
        )

        ctx = {
            "year": year,
            "subcat": subcat,
            "category": subcat.parent,
            "month_labels": month_labels,
            "month_values": month_values,
            "grand_total": grand_total,
            "transactions": txns,
        }
        return render(request, self.template_name, ctx)
