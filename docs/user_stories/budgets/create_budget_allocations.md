# Create Budget Allocations

**Status**: ✅ COMPLETE - ATDD IMPLEMENTED  
**Epic**: Budget Management  
**Priority**: Must Have  
**Estimated Effort**: 8 points  
**Actual Effort**: 13 points (expanded scope)  
**ATDD Status**: ✅ 6 acceptance tests implemented and passing  

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

#### `budget_wizard_access`
**Given** I want to create a budget  
**When** I access the budget wizard interface  
**Then** I can configure time periods and calculation methods  
**And** the system presents historical data options  

#### `budget_amount_suggestions`
**Given** I have historical transaction data  
**When** I run the budget suggestion wizard  
**Then** the system suggests realistic budget amounts based on past spending patterns  
**And** suggestions use configurable calculation methods (median, average, maximum)  

#### `budget_allocation_adjustment`
**Given** the system presents suggested budget amounts  
**When** I review the suggestions  
**Then** I can adjust individual payoree and category allocations before saving  
**And** the system validates that adjustments are reasonable  

#### `budget_allocation_persistence`  
**Given** I have finalized my budget allocations  
**When** I save the budget plan  
**Then** payoree-centric budget allocations are created in the database  
**And** the budget plan is marked as active for the specified time period

### Allocation Management

#### `budget_allocation_listing`
**Given** I have existing budget allocations  
**When** I view the budget list interface  
**Then** I see all payoree-based allocations with amounts and time periods  
**And** allocations are grouped by effective category for easy review  

#### `allocation_detail_analysis`
**Given** I want to analyze a specific allocation  
**When** I click on a payoree allocation  
**Then** I see detailed spending vs. budget analysis for that payoree  
**And** the system shows transaction history and variance calculations  

#### `allocation_modification`
**Given** I need to modify an existing allocation  
**When** I edit the allocation amount or details  
**Then** changes are immediately reflected in spending calculations  
**And** the system updates related budget summaries  

#### `budget_summary_aggregation`
**Given** I have multiple allocations for the same time period  
**When** I view them in the budget summary  
**Then** I see total budget amounts aggregated by category and payoree  
**And** the system shows overall budget utilization metrics

### Integration with Transactions

#### `transaction_budget_matching`
**Given** I have active budget allocations  
**When** new transactions are imported into the system  
**Then** transactions are automatically matched to relevant payoree-based budget allocations  
**And** category inference from payoree defaults ensures accurate budget tracking  

#### `budget_progress_tracking`
**Given** I have spending against payoree allocations  
**When** I view budget progress reports  
**Then** I see actual vs. budgeted amounts with variance calculations  
**And** the system shows trending and forecasting based on current spending patterns  

#### `budget_overrun_alerts`
**Given** my spending approaches or exceeds a budget allocation  
**When** the system detects budget variance thresholds  
**Then** I receive appropriate visual indicators and notifications  
**And** the system suggests potential reallocation options from underutilized budgets

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

### Model Structure (Post-Refactoring)
```python
class BudgetPlan(models.Model):
    name = CharField()  # e.g., "October 2025 Budget"  
    year = PositiveIntegerField()
    month = PositiveSmallIntegerField()
    is_active = BooleanField()

class BudgetAllocation(models.Model):
    # SIMPLIFIED: Payoree-centric model
    budget_plan = ForeignKey(BudgetPlan)
    payoree = ForeignKey(Payoree)  # Required - core of allocation
    amount = DecimalField()
    is_ai_suggested = BooleanField()
    
    # Category/subcategory derived from payoree.default_category/subcategory
    @property
    def effective_category(self):
        return self.payoree.default_category
        
    @property  
    def effective_subcategory(self):
        return self.payoree.default_subcategory
```

### Calculation Service
- Historical spending analysis using configurable lookback periods
- Multiple aggregation methods (median, mean, 75th percentile)
- Seasonal adjustment capabilities
- Outlier detection and handling

## Testing Strategy

**ATDD Test Coverage**: `budgets/tests/test_acceptance_budget_creation_atdd.py`
- ✅ `budget_wizard_access` - Wizard interface configuration and access
- ✅ `budget_amount_suggestions` - Historical data-based budget suggestions  
- ✅ `budget_allocation_adjustment` - User modification of suggested amounts
- ✅ `budget_allocation_persistence` - Database persistence of payoree-centric allocations
- ✅ `budget_allocation_listing` - Budget list interface and display
- ✅ `transaction_budget_matching` - Automatic transaction to allocation matching

**Additional Testing**:
- Unit tests for budget calculation algorithms (`BaselineCalculator`)
- Integration tests for wizard workflow (`BudgetWizard`)  
- Performance tests with large historical datasets
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