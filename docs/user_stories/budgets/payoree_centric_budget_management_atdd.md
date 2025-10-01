# Payoree-Centric Budget Management - Additional ATDD Stories

**Status**: 🚧 IN PROGRESS  
**Epic**: Budget Management Refactoring  
**Priority**: Must Have  
**Estimated Effort**: 15 points  
**ATDD Status**: Shell file for new acceptance test development  

## Overview

This file serves as a collection point for acceptance test driven development (ATDD) stories related to the new payoree-centric budget management system. As we refactor from the complex multi-scope budget system to the simplified payoree-only approach, new acceptance criteria and test scenarios emerge that don't fit existing user story files.

## Architecture Context

The payoree-centric budget refactoring simplifies the budget model from:
```python
# OLD: Complex multi-scope system
BudgetAllocation(
    category=..., subcategory=..., payoree=..., needs_level=..., amount=...
)

# NEW: Simplified payoree-centric system  
BudgetAllocation(
    budget_plan=..., payoree=..., amount=...
    # Categories derived via payoree.default_category
)
```

This architectural change requires new acceptance tests to validate the simplified workflows and ensure the system remains intuitive and functional.

---

## User Story Collection

### 1. Payoree-Only Budget Allocation Creation

**Status**: ⏳ WAITING  
**User Story**: As a **budget planner**, I want to **create budget allocations by specifying only the payoree and amount** so that **budgeting becomes more concrete and actionable around who I actually pay**.

#### Acceptance Criteria

- [ ] ⏳ **payoree_allocation_creation**: Given I want to create a budget allocation, when I select a payoree and enter an amount, then the system creates an allocation with categories automatically derived from the payoree's defaults
- [ ] ⏳ **effective_category_display**: Given a payoree-based allocation exists, when I view the allocation, then I see the effective category and subcategory derived from the payoree
- [ ] ⏳ **payoree_validation**: Given I attempt to create an allocation, when I don't specify a payoree, then the system prevents creation with a clear validation error
- [ ] ⏳ **duplicate_allocation_prevention**: Given an allocation already exists for a payoree in a budget plan, when I try to create another allocation for the same payoree, then the system prevents duplicate creation

#### Test Implementation
```python
# Tests to be created in: budgets/tests/test_payoree_centric_allocation_atdd.py
class TestPayoreeCentricAllocationATDD(TestCase):
    def test_payoree_allocation_creation(self):
        # ATDD ID: payoree_allocation_creation
        pass
        
    def test_effective_category_display(self):
        # ATDD ID: effective_category_display  
        pass
```

---

### 2. Historical Spending Analysis for Payorees

**Status**: ⏳ WAITING  
**User Story**: As a **data-driven budgeter**, I want to **see historical spending patterns by payoree** so that **I can make informed allocation decisions based on actual payment history**.

#### Acceptance Criteria

- [ ] ⏳ **payoree_spending_history**: Given historical transactions exist for a payoree, when I view budget suggestions, then the system shows spending patterns and suggests allocations based on payoree-specific history
- [ ] ⏳ **payoree_baseline_calculation**: Given multiple months of payoree transactions, when the system calculates baselines, then it aggregates spending by payoree rather than by category
- [ ] ⏳ **payoree_trend_analysis**: Given 6+ months of payoree data, when I request trend analysis, then the system shows spending trends per payoree with variance indicators

---

### 3. Misc Payoree Management

**Status**: ⏳ WAITING  
**User Story**: As a **budget manager**, I want to **handle transactions that don't map to specific payorees** so that **I can still include miscellaneous expenses in my budget planning**.

#### Acceptance Criteria

- [ ] ⏳ **misc_payoree_creation**: Given transactions without clear payoree mapping, when I process them, then the system can create or use a "Miscellaneous" payoree for budget allocation
- [ ] ⏳ **misc_category_assignment**: Given a misc payoree allocation, when I set the category, then future misc transactions can be properly categorized for budget tracking
- [ ] ⏳ **misc_allocation_aggregation**: Given multiple misc transactions across categories, when I view budget reports, then misc spending is properly aggregated and displayed

---

### 4. Budget Report Payoree Grouping

**Status**: ⏳ WAITING  
**User Story**: As a **budget reviewer**, I want to **view budget reports grouped by payoree with category context** so that **I understand both who I'm paying and what categories my spending falls into**.

#### Acceptance Criteria

- [ ] ⏳ **payoree_grouped_reporting**: Given budget allocations exist, when I view the budget report, then allocations are grouped by payoree with effective category information displayed
- [ ] ⏳ **category_rollup_display**: Given multiple payorees in the same category, when I view the report, then I can see both payoree-level detail and category-level rollups
- [ ] ⏳ **payoree_variance_analysis**: Given actual spending vs. allocations, when I review variances, then I see both payoree-specific and category-level variance analysis

---

### 5. Budget Wizard Payoree Workflow

**Status**: ⏳ WAITING  
**User Story**: As a **new budget creator**, I want to **use the budget wizard with payoree-focused suggestions** so that **I can quickly create realistic budgets based on who I actually pay**.

#### Acceptance Criteria

- [ ] ⏳ **payoree_suggestion_workflow**: Given I start the budget wizard, when it analyzes my transaction history, then it suggests allocations organized by payoree with recommended amounts
- [ ] ⏳ **payoree_category_inference**: Given suggested payoree allocations, when I review them, then I see inferred categories and can adjust them if needed
- [ ] ⏳ **wizard_payoree_completion**: Given I complete the wizard, when it creates allocations, then all allocations are payoree-based with properly derived category information

---

## Testing Strategy

### Unit Tests
- Model validation and property tests
- Service method functionality 
- Edge cases and error handling

### Integration Tests  
- Database constraint validation
- Service integration workflows
- Model relationship integrity

### ATDD Acceptance Tests
- User workflow validation
- End-to-end feature testing
- Cross-component integration

### Performance Tests
- Historical data aggregation performance
- Report generation with large datasets
- Database query optimization validation

---

## Implementation Notes

### Priority Order
1. **Payoree-Only Allocation Creation** - Core functionality needed first
2. **Historical Spending Analysis** - Enables informed decision making
3. **Budget Report Grouping** - User interface and reporting
4. **Misc Payoree Management** - Edge case handling
5. **Budget Wizard Updates** - Enhanced user experience

### Dependencies
- Payoree model with default_category relationship
- Updated BaselineCalculator service
- Simplified BudgetAllocation model
- Updated admin interface

### Migration Strategy
- Clean slate migration already implemented
- Legacy data handling via utility scripts
- Gradual service method updates
- Template and view updates

---

## Related Stories

### Existing Stories
- [Create Budget Allocations](create_budget_allocations.md) - Core allocation functionality
- [Budget Report Classification Round Trip](budger_report_classification_round_trip_atdd.md) - Navigation patterns
- [Multiple Budget Plans](create_multiple_budget_plans.md) - Multi-plan support

### Future Enhancements
- Advanced payoree categorization rules
- Payoree-based recurring budget templates
- Collaborative payoree budget planning
- Integration with payoree contact management

---

## Conversion to ATDD Format

As acceptance criteria are developed and tested, they should be converted to full ATDD format with:
1. **Unique Test IDs** for each criterion
2. **Gherkin-style scenarios** (Given/When/Then)
3. **Linked test implementation** in the codebase
4. **Automated test execution** in CI/CD pipeline

New ATDD test files should be created in `budgets/tests/` following the naming convention:
- `test_acceptance_payoree_allocation_atdd.py`
- `test_acceptance_payoree_reporting_atdd.py`  
- `test_acceptance_payoree_wizard_atdd.py`

This ensures comprehensive test coverage for the payoree-centric budget management system.