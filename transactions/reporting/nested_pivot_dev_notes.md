# transactions/reporting/nested_pivot.py - Developer Notes

## Overview

`nested_pivot.py` implements a sophisticated nested pivot table system for Django models, specifically designed for hierarchical financial reporting. It transforms flat transaction data into nested tree structures with monthly aggregations, enabling complex budget reports with multiple levels of categorization.

## Architecture

### Core Components

#### 1. `NestedPivotSpec` (DataClass)
Configuration object that defines the pivot operation:

```python
@dataclass
class NestedPivotSpec:
    dims: list[str]                 # Dimension hierarchy (e.g., ["type", "category", "subcategory"])
    metric_expr: str = "amount"     # Field to aggregate (default: "amount")
    filters: Q | None = None        # Django Q filters
    start: date | None = None       # Date range start
    end: date | None = None         # Date range end
    extras: list[str] | None = None # Extra fields to include at leaves
```

#### 2. `_month_edges()` Function
Generates monthly date ranges for aggregation:

- **Input**: `start_date`, `end_date`
- **Output**: List of `(first_day, last_day, 'YYYY-MM')` tuples
- **Purpose**: Defines monthly buckets for pivot aggregation

#### 3. `nested_budget_data()` Function
Main orchestration function that:

1. **Validates** spec requirements (start/end dates)
2. **Filters** transaction queryset
3. **Generates** monthly date ranges
4. **Builds** conditional aggregations using Django's `Case`/`When`
5. **Constructs** nested tree structure
6. **Returns** `{"tree": nested_dict, "months": [labels]}`

## Data Flow

```
Transaction.objects.all()
    ↓ filter(spec.filters)
    ↓ annotate(monthly_sums)
    ↓ values(dims + extras)
    ↓ build_nested_tree()
    ↓ {"tree": {...}, "months": [...]}
```

## Tree Structure

The output tree is a nested dictionary where:

- **Intermediate nodes**: Regular dict keys representing dimension values
- **Leaf nodes**: Contain special keys:
  - `"__cells__"`: List of monthly aggregated values
  - `"__extra__"`: Dict of extra field values (if specified)

### Example Tree Structure

```python
{
    "expense": {
        "Needs": {
            "Food": {
                "Groceries": {
                    "__cells__": [100.00, 150.00, 200.00, ...],  # 12 months
                    "__extra__": {"subcategory_id": 1}
                },
                "Restaurants": {
                    "__cells__": [50.00, 75.00, 100.00, ...],
                    "__extra__": {"subcategory_id": 2}
                }
            }
        }
    },
    "income": {
        "Salary": {
            "__cells__": [3000.00, 3000.00, 3000.00, ...],
            "__extra__": {"subcategory_id": 3}
        }
    }
}
```

### Enhanced Tree with Intermediate Totals

For more advanced reporting, you can modify the tree building logic to include monthly totals at each nesting level:

```python
def nested_budget_data_with_totals(spec: NestedPivotSpec) -> dict:
    # ... existing code ...
    
    # Build nested tree with intermediate totals
    root: dict = {}
    labels = [label for *_, label in months]

    for row in row_dicts:
        cursor = root
        path = []  # Track path for calculating parent totals
        
        for dim in spec.dims:
            key = row[dim]
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
    # CRITICAL FIX: Only add to parent levels, not all ancestors (prevents double-counting)
    for i, key in enumerate(path[:-1]):  # Exclude the last element (leaf node)
        if key not in current:
            current[key] = {}
        
        current = current[key]
        
        # Initialize or update totals for this level
        if "__cells__" not in current:
            current["__cells__"] = [Decimal("0")] * len(labels)
        
        # Add leaf values to this parent level only
        for j, value in enumerate(cells):
            if value is not None:
                current["__cells__"][j] += Decimal(str(value))
        
        # Mark as intermediate node
        current["__is_intermediate__"] = True

## Critical Bug Fix: Double-Counting Prevention

**Issue**: The original implementation was adding transaction amounts to EVERY level in the hierarchy path, causing totals to be multiplied by the depth of the hierarchy.

**Example**: For path `["expense", "Needs", "Food", "Groceries"]`, a $100 transaction was being added to:
- expense level: +$100 ❌ (should be +$100)
- Needs level: +$100 ❌ (should be +$100) 
- Food level: +$100 ❌ (should be +$100)
- Groceries level: +$100 ✅ (correct)

**Result**: Top-level totals were 3-4x higher than actual values.

**Fix**: Changed `for i, key in enumerate(path):` to `for i, key in enumerate(path[:-1]):` to exclude the leaf node from parent total calculations.

**Impact**: Ensures each transaction is counted exactly once per hierarchy level, providing accurate intermediate totals.
```

### Enhanced Tree Structure with Totals

```python
{
    "expense": {
        "__cells__": [1500.00, 1800.00, 2100.00, ...],  # Total of all expenses
        "__is_intermediate__": true,
        "Needs": {
            "__cells__": [1200.00, 1450.00, 1700.00, ...],  # Total of all needs
            "__is_intermediate__": true,
            "Food": {
                "__cells__": [900.00, 1100.00, 1300.00, ...],  # Total of all food
                "__is_intermediate__": true,
                "Groceries": {
                    "__cells__": [600.00, 750.00, 900.00, ...],  # Leaf data
                    "__extra__": {"subcategory_id": 1}
                },
                "Restaurants": {
                    "__cells__": [300.00, 350.00, 400.00, ...],  # Leaf data
                    "__extra__": {"subcategory_id": 2}
                }
            }
        }
    }
}
```

### Benefits of Intermediate Totals

1. **Progressive Disclosure**: Show summary totals before drilling down
2. **Quick Overview**: See category totals without expanding all subcategories
3. **Better UX**: Users can quickly identify which categories have the most activity
4. **Performance**: Calculate totals once during data processing instead of in templates
5. **Consistency**: Ensure all totals are calculated the same way

### Template Usage with Intermediate Totals

```html
<!-- transactions/_report_budget_row.html -->
<tr>
  <td style="padding-left: {{ level|mul:20 }}px;">
    {% if node.__is_intermediate__ %}
      <strong>{{ node.label }}</strong>
    {% else %}
      {{ node.label }}
    {% endif %}
  </td>
  {% for cell in node.cells %}
    <td class="text-end">
      {% if node.__is_intermediate__ %}
        <strong>{{ cell|floatformat:2 }}</strong>
      {% else %}
        {{ cell|floatformat:2 }}
      {% endif %}
    </td>
  {% endfor %}
  <td class="text-end">
    {% if node.__is_intermediate__ %}
      <strong>{{ node.row_total|floatformat:2 }}</strong>
    {% else %}
      {{ node.row_total|floatformat:2 }}
    {% endif %}
  </td>
</tr>

<!-- Recursively include children -->
{% for child in node.children %}
  {% include "transactions/_report_budget_row.html" with node=child level=node.level|add:1 %}
{% endfor %}
```

## Usage Examples

### Basic Budget Report

```python
from transactions.reporting.nested_pivot import NestedPivotSpec, nested_budget_data
from datetime import date

spec = NestedPivotSpec(
    dims=[
        "subcategory__parent__type",    # expense/income
        "subcategory__parent__name",    # Needs/Wants/Savings
        "subcategory__name"             # specific subcategory
    ],
    metric_expr="amount",
    start=date(2025, 1, 1),
    end=date(2025, 12, 31),
    extras=["subcategory__id"]
)

result = nested_budget_data(spec)
# result["tree"] contains nested hierarchy
# result["months"] contains ["2025-01", "2025-02", ...]
```

### Filtered Report (Expenses Only)

```python
from django.db.models import Q

spec = NestedPivotSpec(
    dims=["subcategory__parent__name", "subcategory__name"],
    filters=Q(subcategory__parent__type="expense"),
    start=date(2025, 1, 1),
    end=date(2025, 12, 31)
)
```

## Performance Considerations

### Optimizations Implemented

1. **Single Query**: Uses one database query with conditional aggregations
2. **Indexed Values**: `values(*dims)` leverages database indexes
3. **Efficient Annotations**: Django's `Case`/`When` for conditional sums
4. **Memory Efficient**: Streams results without loading all rows at once

### Potential Bottlenecks

1. **Memory Usage**: Large result sets with many dimensions
2. **Query Complexity**: Multiple `Case`/`When` conditions for many months
3. **Tree Building**: In-memory tree construction for large hierarchies

### Recommended Mitigations

1. **Pagination**: Limit date ranges for large datasets
2. **Filtering**: Use `spec.filters` to reduce dataset size
3. **Indexing**: Ensure database indexes on dimension fields
4. **Caching**: Cache results for frequently accessed reports

## Integration Points

### Views Integration

```python
# transactions/views/report_budget.py
class BudgetNestedReportView(View):
    def get(self, request):
        spec = NestedPivotSpec(
            dims=["subcategory__parent__type", "subcategory__parent__name", "subcategory__name"],
            start=date(2025, 1, 1),
            end=date(2025, 12, 31)
        )

        data = nested_budget_data(spec)
        nodes = self._tree_to_nodes(data["tree"])

        return render(request, self.template_name, {
            "nodes": nodes,
            "month_labels": data["months"]
        })
```

### Template Integration

```html
<!-- Recursive template rendering -->
{% for node in nodes %}
  {% include "transactions/_report_budget_row.html" with node=node level=0 %}
{% endfor %}
```

## Error Handling

### Validation
- **Required**: `start` and `end` dates must be provided
- **Type Safety**: Uses type hints and assertions for critical parameters

### Edge Cases
- **Empty Results**: Returns empty tree structure
- **Missing Dimensions**: Handles `None` values in dimension fields
- **Date Ranges**: Validates date range logic in `_month_edges()`

## Testing Strategy

### Unit Tests
- Test `_month_edges()` with various date ranges
- Test tree building with mock data
- Test filtering and aggregation logic

### Integration Tests
- Test with real Transaction data
- Test template rendering with nested data
- Test performance with large datasets

## Future Enhancements

### Potential Improvements

1. **Async Support**: Add async/await for large datasets
2. **Caching Layer**: Redis/memcached integration
3. **Export Formats**: CSV/Excel export capabilities
4. **Custom Aggregations**: Support for AVG, COUNT, etc.
5. **Time Granularity**: Support for weekly/daily pivots
6. **Drill-down Caching**: Cache intermediate tree levels

### API Extensions

```python
# Future API possibilities
class NestedPivotSpec:
    # Add support for:
    time_granularity: str = "month"  # "day", "week", "quarter"
    aggregation_type: str = "sum"    # "avg", "count", "min", "max"
    sort_order: list[str] = None      # Custom sorting
    limit: int = None                 # Row limiting
```

## Dependencies

### Django Components
- `django.db.models`: QuerySet, aggregations, Case/When
- `django.db.models.Q`: Query filtering
- `django.db.models.F`: Field references

### Python Standard Library
- `dataclasses`: Configuration objects
- `datetime.date`: Date handling
- `calendar.monthrange`: Month calculations
- `typing`: Type hints

### Project Dependencies
- `transactions.models.Transaction`: Data source
- `transactions.utils.trace`: Debug logging decorator

## Debugging

### Common Issues

1. **Empty Results**: Check date ranges and filters
2. **Memory Errors**: Reduce date range or add filtering
3. **Performance**: Add database indexes on dimension fields

### Debug Output

The `@trace` decorator provides detailed logging for:
- Query execution
- Tree building process
- Performance metrics

## Conclusion

`nested_pivot.py` provides a robust, efficient solution for hierarchical financial reporting in Django applications. Its design balances flexibility, performance, and maintainability, making it suitable for complex budget analysis and reporting needs.

The modular architecture allows for easy extension and customization while maintaining clean separation of concerns between data aggregation, tree building, and presentation layers.
