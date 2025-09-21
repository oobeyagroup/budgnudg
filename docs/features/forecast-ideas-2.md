# FORECAST_IDEAS_2.md - Payoree-Based Recurring Transaction Detection
*Supersedes FORECAST_IDEAS.md*

## Overview
This document outlines the enhanced recurring transaction detection system that uses payoree-based categorization instead of merchant keys. The system automatically discovers recurring patterns in transaction data and provides weekly-organized forecasting capabilities.

## Core Architecture

### Data Model
```python
# transactions/models.py
class RecurringSeries(models.Model):
    INTERVAL_CHOICES = [
        ("weekly", "Weekly"),
        ("biweekly", "Biweekly"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("yearly", "Yearly"),
    ]

    # Payoree-based identity (replaces merchant_key)
    payoree = models.ForeignKey("Payoree", null=True, blank=True, on_delete=models.SET_NULL)
    amount_cents = models.IntegerField()
    amount_tolerance_cents = models.IntegerField(default=100)

    # Cadence & status
    interval = models.CharField(max_length=20, choices=INTERVAL_CHOICES)
    confidence = models.FloatField(default=0.0)
    first_seen = models.DateField()
    last_seen = models.DateField()
    next_due = models.DateField(null=True, blank=True)

    # Lifecycle
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["payoree", "amount_cents"]),
            models.Index(fields=["next_due"]),
            models.Index(fields=["active"]),
        ]

    def __str__(self) -> str:
        payoree_name = self.payoree.name if self.payoree else "Unknown"
        return f"{payoree_name} • {self.interval} • ${self.amount_cents/100:.2f}"
```

### Key Changes from Previous Version
- **Removed `merchant_key` field** - Now uses payoree foreign key exclusively
- **Payoree-centric grouping** - Transactions grouped by payoree instead of extracted merchant names
- **Simplified key generation** - Uses payoree.name directly instead of merchant extraction
- **Enhanced weekly organization** - Forecast results organized by weeks for better planning

## Detection Service

### Core Functions
```python
# transactions/services/recurring.py

def payoree_key_for(transaction: Transaction) -> str:
    """Generate grouping key from payoree name."""
    if transaction.payoree and transaction.payoree.name:
        return transaction.payoree.name.strip().lower()
    return "unknown"

def seed_series_from_transaction(transaction: Transaction) -> RecurringSeries:
    """Create or update recurring series from a single transaction."""
    key = payoree_key_for(transaction)
    amount_bucket = _bucket_amount(_to_cents(transaction.amount))

    # Find existing series for this payoree/amount combination
    existing = RecurringSeries.objects.filter(
        payoree=transaction.payoree,
        amount_cents=amount_bucket
    ).first()

    if existing:
        # Update existing series
        existing.last_seen = max(existing.last_seen, transaction.date)
        existing.save()
        return existing

    # Create new series
    return RecurringSeries.objects.create(
        payoree=transaction.payoree,
        amount_cents=amount_bucket,
        interval="monthly",  # Default guess
        confidence=0.6,
        first_seen=transaction.date,
        last_seen=transaction.date,
        active=True,
        notes="Auto-detected from transaction patterns"
    )
```

### Detection Algorithm
1. **Group by Payoree**: Transactions grouped by payoree name and amount buckets
2. **Analyze Patterns**: Examine date sequences for regular intervals
3. **Calculate Confidence**: Score based on regularity and consistency
4. **Generate Predictions**: Create upcoming transaction predictions

## Enhanced Forecasting

### Weekly Organization
```python
# transactions/selectors.py

def build_upcoming_forecast(weeks: int = 4) -> dict:
    """
    Build weekly-organized forecast with recurring predictions.

    Returns:
    {
        "week_starts": [date, ...],
        "projected_weekly_totals": [float, ...],
        "weekly_details": {week_start: {"by_category": {...}, "recurring": [...]}},
        "recurring_predictions": [{"payoree": str, "amount": float, "next_date": date, ...}],
        "designated_recurring": [RecurringSeries, ...]
    }
    """
```

### Key Features
- **Payoree-based grouping** for recurring detection
- **Weekly organization** of forecast results
- **Confidence scoring** for pattern reliability
- **Flexible intervals** (weekly, biweekly, monthly, quarterly, yearly)
- **Amount tolerance** handling for slight variations

## UI Components

### Recurring Series List
- Table showing payoree, amount, interval, confidence, next due date
- Color-coded status indicators (upcoming, due, overdue)
- Links to detailed views and transaction history

### Enhanced Templates
```html
<!-- transactions/templates/transactions/recurring_list.html -->
<table class="table">
  <thead>
    <tr>
      <th>Payoree</th>
      <th>Amount</th>
      <th>Interval</th>
      <th>Confidence</th>
      <th>Next Due</th>
      <th>Status</th>
    </tr>
  </thead>
  <tbody>
    {% for series in series %}
    <tr>
      <td>
        <a href="{% url 'recurring_detail' series.pk %}">
          {{ series.payoree.name|default:"Unknown" }}
        </a>
      </td>
      <td>${{ series.amount_cents|floatformat:-2 }}</td>
      <td>{{ series.interval|title }}</td>
      <td>{{ series.confidence|floatformat:2 }}</td>
      <td>{{ series.next_due|default:"—" }}</td>
      <td>
        {% if series.next_due %}
          {% if series.next_due < today %}
            <span class="badge bg-danger">Overdue</span>
          {% elif series.next_due == today %}
            <span class="badge bg-warning">Due Today</span>
          {% else %}
            <span class="badge bg-success">Upcoming</span>
          {% endif %}
        {% endif %}
      </td>
    </tr>
    {% endfor %}
  </tbody>
</table>
```

## Integration Points

### Transaction Processing
- Automatic recurring detection during data ingestion
- Payoree assignment triggers pattern analysis
- Confidence updates based on new transaction data

### Admin Interface
```python
# transactions/admin.py
@admin.register(RecurringSeries)
class RecurringSeriesAdmin(admin.ModelAdmin):
    list_display = ("payoree", "amount_cents", "interval", "confidence", "last_seen", "next_due", "active")
    list_filter = ("interval", "active", "payoree")
    search_fields = ("payoree__name",)
    readonly_fields = ("first_seen", "last_seen")
```

### API Endpoints
- `/transactions/recurring/` - List recurring series
- `/transactions/recurring/<pk>/` - Series details
- `/transactions/recurring/from-txn/<pk>/` - Create series from transaction
- `/transactions/report_upcoming/` - Weekly forecast view

## Testing Strategy

### Unit Tests
- Payoree key generation
- Interval detection algorithms
- Confidence scoring
- Amount bucketing logic

### Integration Tests
- Full detection pipeline
- Forecast generation
- UI interactions

### Edge Cases
- Transactions without payoree assignment
- Irregular payment amounts
- Seasonal payment patterns
- Payoree name changes

## Migration Path

### From Merchant-Key to Payoree-Based
1. **Data Migration**: Convert existing merchant_key entries to payoree relationships
2. **Fallback Logic**: Handle transactions without payoree using description extraction
3. **Gradual Transition**: Support both approaches during migration period

### Database Changes
```sql
-- Migration example
ALTER TABLE transactions_recurringseries DROP COLUMN merchant_key;
ALTER TABLE transactions_recurringseries ADD COLUMN payoree_id INTEGER REFERENCES transactions_payoree(id);
CREATE INDEX idx_recurring_payoree_amount ON transactions_recurringseries(payoree_id, amount_cents);
```

## Benefits of Payoree-Based Approach

1. **Consistency**: Leverages existing payoree categorization system
2. **Accuracy**: Uses user-verified payoree assignments
3. **Maintainability**: Fewer moving parts, less merchant extraction logic
4. **User Control**: Users can adjust payoree assignments to improve detection
5. **Integration**: Seamless integration with existing categorization workflows

## Future Enhancements

- Machine learning-based confidence scoring
- Seasonal pattern detection
- Multi-payoree series support
- Automated payoree suggestion for uncategorized transactions
- Integration with budgeting and cash flow planning tools

---

*This document reflects the current payoree-based implementation that supersedes the merchant-key approach outlined in FORECAST_IDEAS.md.*
