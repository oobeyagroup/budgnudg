# Create Budget Allocations

**Status**: 🔄 NEEDS TESTS  
**Epic**: Budget Management  
**Priority**: Must Have  
**Estimated Effort**: 8 points  
**Actual Effort**: 13 points (expanded scope)  
**ATDD Status**: No acceptance tests linked to criteria  

## User Story

As a **budget-conscious user**, I want to **create spending allocations for different categories and time periods** so that **I can plan my expenses and track against my spending goals**.

## Business Context

Budget allocations are the core functionality of the system. Users need to:
- Set spending limits for categories (groceries, utilities, entertainment)
- Create time-bound budgets (monthly, quarterly)
- Use historical data to inform realistic budget amounts
- Track progress against allocated amounts

## Acceptance Criteria

### Budget Creation Workflow
- [ ] ✅ Given I want to create a budget, when I access the budget wizard, then I can configure time periods and calculation methods
- [ ] ✅ Given historical transaction data, when I run the wizard, then it suggests budget amounts based on past spending
- [ ] ✅ Given suggested amounts, when I review them, then I can adjust individual allocations before saving
- [ ] ✅ Given I finalize my budget, when I save, then budget allocations are created in the database

> **⚠️ ATDD Note**: These acceptance criteria need to be converted to the ATDD format with unique IDs and linked to automated tests before this story can be marked as COMPLETED. See `import_csv_transactions_atdd.md` for the required format.

### Allocation Management
- [ ] ✅ Given existing budget allocations, when I view the budget list, then I see all allocations with amounts and time periods
- [ ] ✅ Given a specific allocation, when I click on it, then I see detailed spending vs. budget analysis
- [ ] ✅ Given I need to modify an allocation, when I edit it, then changes are reflected in spending calculations
- [ ] ✅ Given multiple allocations for the same period, when I view them together, then I see total budget summary

### Integration with Transactions
- [ ] ✅ Given budget allocations exist, when new transactions are imported, then they're automatically matched to relevant budget categories
- [ ] ✅ Given spending against an allocation, when I view budget progress, then I see actual vs. budgeted amounts with variance
- [ ] ✅ Given I exceed a budget allocation, when the system detects this, then I receive appropriate visual indicators

## MoSCoW Prioritization

### Must Have ✅
- Budget allocation creation interface
- Integration with historical transaction analysis
- Basic budget vs. actual reporting
- Category-based allocation structure
- Monthly budget periods

### Should Have ✅
- AI-powered budget suggestions based on spending patterns
- Multiple calculation methods (median, average, maximum)
- Budget adjustment and editing capabilities
- Visual progress indicators and charts
- Empty state handling for new users

### Could Have ✅
- Flexible time periods (weekly, quarterly, annual)
- Subcategory and payoree-level allocations  
- Needs-level budget allocation (critical, core, lifestyle)
- Budget templates and presets
- Collaborative budget planning

### Won't Have (Current Version)
- ❌ Multiple budget scenarios (lean/normal/splurge) - *Note: Architecture supports this*
- ❌ Goal-based budgeting (saving for vacation, etc.)
- ❌ Dynamic budget adjustments based on income changes
- ❌ Integration with investment/savings account planning

## Technical Implementation Notes

**Models**: `BudgetPlan`, `BudgetAllocation`, relationship with `Transaction` and `Category`  
**Services**: `BudgetWizard`, `BaselineCalculator` for historical analysis  
**Views**: `BudgetWizardView`, `BudgetListView`, `BudgetDetailView`  
**Templates**: Wizard interface, allocation management, reporting views  
**APIs**: Budget suggestion and commitment endpoints

## Architecture Decisions

### Model Structure
```python
class BudgetPlan(models.Model):
    name = CharField()  # e.g., "October 2025 Budget"  
    year = PositiveIntegerField()
    month = PositiveSmallIntegerField()
    is_active = BooleanField()

class BudgetAllocation(models.Model):
    budget_plan = ForeignKey(BudgetPlan)
    category = ForeignKey(Category, null=True)
    subcategory = ForeignKey(Category, null=True) 
    payoree = ForeignKey(Payoree, null=True)
    needs_level = CharField(null=True)
    amount = DecimalField()
    is_ai_suggested = BooleanField()
```

### Calculation Service
- Historical spending analysis using configurable lookback periods
- Multiple aggregation methods (median, mean, 75th percentile)
- Seasonal adjustment capabilities
- Outlier detection and handling

## Testing Strategy

- Unit tests for budget calculation algorithms
- Integration tests for wizard workflow
- Performance tests with large historical datasets  
- User acceptance testing for budget creation flow
- Edge case testing (no historical data, outlier months)

## Success Metrics

- ✅ Users complete budget creation in under 5 minutes
- ✅ 85%+ of suggested allocations are accepted without modification
- ✅ Budget variance tracking shows actual vs. planned spending
- ✅ System handles users with 0-24 months of historical data
- ✅ Allocation creation scales to 50+ categories per budget

## Future Enhancement Ideas

Based on completed implementation:

1. **Multi-scenario budgets**: Leverage existing BudgetPlan architecture for lean/normal/splurge scenarios
2. **Smart reallocation**: Suggest moving unused budget from one category to another
3. **Seasonal patterns**: Detect and account for seasonal spending variations
4. **Budget roll-over**: Handle unused budget amounts in subsequent periods

## Lessons Learned

- **Historical data complexity**: Users have varying amounts and quality of historical data
- **User preferences**: Some users prefer conservative budgets, others optimistic - need flexibility
- **Performance considerations**: Budget calculations with large datasets require optimization
- **User workflow**: Preview and adjustment phase critical for user adoption
- **Model design**: BudgetPlan + BudgetAllocation separation provides excellent flexibility for future enhancements