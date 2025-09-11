# transactions/views/pivot_table.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, List

from django.shortcuts import render
from django.views import View
from django.db.models import Sum, Case, When, DecimalField, F, Q, Value
from django import forms
from django.utils.decorators import method_decorator

from transactions.models import Transaction
from transactions.utils import trace


class PivotTableForm(forms.Form):
    """Form for selecting pivot table dimensions."""

    # Available row fields (excluding Sheet Account and Account Type as requested)
    ROW_FIELD_CHOICES = [
        ('category__name', 'Category'),
        ('subcategory__name', 'Subcategory'),
        ('category__type', 'Category Type'),
        ('payoree__name', 'Payoree'),
        ('bank_account__name', 'Bank Account'),
    ]

    row_fields = forms.MultipleChoiceField(
        choices=ROW_FIELD_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Row Fields (order matters for nesting)",
        help_text="Select and order the fields to use as nested rows"
    )

    year = forms.IntegerField(
        initial=date.today().year,
        min_value=2000,
        max_value=2030,
        label="Year"
    )

    include_uncategorized = forms.BooleanField(
        required=False,
        initial=True,
        label="Include uncategorized transactions"
    )


class FlexiblePivotTableView(View):
    template_name = "transactions/pivot_table.html"

    @method_decorator(trace)
    def get(self, request):
        form = PivotTableForm(request.GET or None)

        if form.is_valid():
            # Get selected row fields
            row_fields = form.cleaned_data['row_fields']
            year = form.cleaned_data['year']
            include_uncategorized = form.cleaned_data['include_uncategorized']

            # Generate pivot data
            pivot_data = self._generate_pivot_data(
                row_fields=row_fields,
                year=year,
                include_uncategorized=include_uncategorized
            )

            context = {
                'form': form,
                'pivot_data': pivot_data,
                'year': year,
                'row_fields': row_fields,
            }
        else:
            context = {
                'form': form,
                'pivot_data': None,
            }

        return render(request, self.template_name, context)

    def _generate_pivot_data(self, row_fields: List[str], year: int, include_uncategorized: bool) -> dict:
        """Generate nested pivot table data with hierarchical structure."""

        # Create filters
        filters = Q(date__year=year)
        if not include_uncategorized:
            filters &= Q(category__isnull=False)

        # Get month edges for the year
        months = self._get_month_edges(year)

        # Build conditional month sums
        month_annos = {}
        for first, last, display_date in months:
            month_key = f"{display_date.year:04d}-{display_date.month:02d}"
            month_annos[month_key] = Sum(
                Case(
                    When(date__gte=first, date__lte=last, then=F('amount')),
                    default=Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            )

        # Query the data with all selected dimensions
        qs = Transaction.objects.filter(filters)
        row_dicts = qs.values(*row_fields).annotate(**month_annos).order_by(*row_fields)

        # Build hierarchical tree structure
        root = {}
        month_labels = [display_date for *_, display_date in months]

        for row in row_dicts:
            current = root
            path = []

            # Build nested structure
            for field in row_fields:
                key = row.get(field)
                if key is None:
                    key = "Uncategorized"
                path.append(key)

                if key not in current:
                    current[key] = {}
                current = current[key]

            # Add monthly data at leaf level
            monthly_values = []
            for display_date in month_labels:
                month_key = f"{display_date.year:04d}-{display_date.month:02d}"
                monthly_values.append(row.get(month_key, Decimal('0')))
            current['__monthly__'] = monthly_values
            current['__total__'] = sum(monthly_values)

        # Convert tree to nested nodes for template
        nodes = self._tree_to_nodes(root, row_fields)

        # Calculate column totals
        column_totals = []
        for i in range(len(month_labels)):
            column_total = sum(
                node.get('monthly_values', [Decimal('0')] * len(month_labels))[i]
                for node in self._flatten_nodes(nodes)
            )
            column_totals.append(column_total)

        grand_total = sum(column_totals)

        return {
            'nodes': nodes,
            'month_labels': month_labels,
            'column_totals': column_totals,
            'grand_total': grand_total,
            'row_fields': row_fields,
        }

    def _tree_to_nodes(self, tree: dict, row_fields: List[str], level: int = 0, parent_path: List[str] = None) -> List[dict]:
        """Convert tree structure to nested nodes for template."""
        if parent_path is None:
            parent_path = []

        nodes = []

        for key, value in tree.items():
            if key.startswith('__'):
                continue  # Skip special keys

            current_path = parent_path + [key]
            node = {
                'label': key,
                'level': level,
                'path': current_path,
                'field_name': row_fields[level] if level < len(row_fields) else '',
                'children': [],
                'has_children': isinstance(value, dict) and any(not k.startswith('__') for k in value.keys()),
            }

            # If this is a leaf node (has monthly data)
            if '__monthly__' in value:
                node['monthly_values'] = value['__monthly__']
                node['total'] = value['__total__']
                node['is_leaf'] = True
            else:
                node['is_leaf'] = False
                node['monthly_values'] = [Decimal('0')] * 12  # Placeholder
                node['total'] = Decimal('0')

            # Recursively process children
            if isinstance(value, dict):
                child_nodes = self._tree_to_nodes(value, row_fields, level + 1, current_path)
                node['children'] = child_nodes

                # Calculate totals from children
                if not node['is_leaf']:
                    for child in child_nodes:
                        for i, val in enumerate(child['monthly_values']):
                            if i < len(node['monthly_values']):
                                node['monthly_values'][i] += val
                        node['total'] += child['total']

            nodes.append(node)

        return nodes

    def _flatten_nodes(self, nodes: List[dict]) -> List[dict]:
        """Flatten nested nodes to get all leaf nodes."""
        result = []
        for node in nodes:
            if node.get('is_leaf'):
                result.append(node)
            else:
                result.extend(self._flatten_nodes(node.get('children', [])))
        return result

    def _get_month_edges(self, year: int) -> List[tuple]:
        """Get month start/end dates for the year."""
        from calendar import monthrange

        months = []
        for month in range(1, 13):
            first_day = date(year, month, 1)
            last_day = date(year, month, monthrange(year, month)[1])
            # Create a date object for the first day of the month for template display
            display_date = date(year, month, 1)
            label = f"{year:04d}-{month:02d}"
            months.append((first_day, last_day, display_date))

        return months
