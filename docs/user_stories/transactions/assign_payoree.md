# Assign Payoree to Transactions

**Status**: ✅ COMPLETED  
**Epic**: Transaction Management  
**Priority**: Must Have  
**Estimated Effort**: 3 points  
**Actual Effort**: 5 points  

## User Story

As a **budget tracker**, I want to **assign payorees to my transactions** so that **I can analyze spending patterns by merchant/vendor and create more accurate budget allocations**.

## Business Context

Knowing who transactions are with (merchants, employers, service providers) enables:
- Spending pattern analysis by vendor
- Automatic categorization based on payoree history
- Budget allocation optimization
- Duplicate transaction detection

## Acceptance Criteria

### Core Assignment Functionality
- [ ] ✅ Given a transaction with no payoree, when I view the transaction list, then I can select a payoree from a dropdown
- [ ] ✅ Given a payoree name I type, when it matches existing payorees, then I see autocomplete suggestions
- [ ] ✅ Given a new payoree name, when I enter it, then a new payoree record is created automatically
- [ ] ✅ Given I assign a payoree to a transaction, when I save, then the assignment persists in the database

### Bulk Operations
- [ ] ✅ Given multiple transactions with no payoree, when I select them and choose "Assign Payoree", then I can assign the same payoree to all selected transactions
- [ ] ✅ Given transactions with similar descriptions, when I assign a payoree to one, then the system suggests the same payoree for similar transactions
- [ ] ✅ Given I want to reassign payorees, when I bulk select transactions, then I can change their payoree assignments

### Smart Matching
- [ ] ✅ Given transaction descriptions containing merchant names, when I import transactions, then the system automatically suggests matching payorees
- [ ] ✅ Given a payoree has been used before, when similar transaction descriptions appear, then that payoree is auto-suggested
- [ ] ✅ Given partial matches in descriptions, when I'm assigning payorees, then I see ranked suggestions based on similarity

## MoSCoW Prioritization

### Must Have ✅
- Manual payoree assignment to individual transactions
- Payoree creation during assignment
- Basic autocomplete functionality
- Persistence of assignments

### Should Have ✅  
- Bulk payoree assignment
- Smart suggestions based on description matching
- Transaction filtering by payoree
- Payoree management interface (edit, merge, delete)

### Could Have ✅
- Machine learning-based payoree prediction
- Automatic payoree assignment rules
- Payoree aliases (multiple names for same entity)
- Import payoree mapping from CSV

### Won't Have (Current Version)
- ❌ Integration with merchant databases
- ❌ Payoree logo/branding display  
- ❌ Location-based payoree suggestions
- ❌ Social media integration for payoree info

## Technical Implementation Notes

**Files**: `transactions/views.py`, `transactions/models.py`, `transactions/admin.py`  
**Models**: Payoree, Transaction (ForeignKey relationship)  
**Templates**: `transactions/list.html`, `transactions/payoree_list.html`  
**JavaScript**: Autocomplete functionality in transaction forms

## Testing Strategy

- Unit tests for payoree matching algorithms
- Integration tests for bulk assignment workflows
- Performance tests with large transaction datasets
- User workflow testing for assignment efficiency

## Success Metrics

- ✅ 90%+ of transactions have assigned payorees after 2 weeks of use
- ✅ Average time to assign payoree: under 5 seconds per transaction
- ✅ Smart suggestions accuracy: 80%+ correct matches
- ✅ Zero duplicate payoree creation for same merchant variants

## Database Design

```sql
-- Payoree model structure
class Payoree(models.Model):
    name = models.CharField(max_length=200, unique=True)
    default_category = models.ForeignKey(Category, null=True)
    default_subcategory = models.ForeignKey(Category, null=True) 
    default_needs_level = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

-- Transaction relationship  
class Transaction(models.Model):
    payoree = models.ForeignKey(Payoree, null=True, blank=True)
    # ... other fields
```

## Lessons Learned

- **Name variations**: Same merchant appears with different names in bank feeds
- **User workflow**: Bulk operations essential for user efficiency
- **Data quality**: Autocomplete prevents typo-induced duplicates
- **Performance**: Need indexed searches for large payoree lists