# Budget by Classification Analysis

**Status**: 🚧 IN PROGRESS  
**Epic**: Budget Management  
**Priority**: High  
**Effort**: Medium (3-5 days)  
**Dependencies**: BudgetPlan and BudgetAllocation models  

## Related User Stories

### Budget Management Dependencies
- [`docs/user_stories/budgets/create_multiple_budget_plans.md`](../budgets/create_multiple_budget_plans.md) - Multiple budget scenarios (lean/normal/splurge)
- [`docs/user_stories/budgets/create_budget_allocations.md`](../budgets/create_budget_allocations.md) - Core budget allocation functionality

### Transaction Analysis Synergies  
- [`docs/user_stories/transactions/advanced_search_filtering.md`](../transactions/advanced_search_filtering_atdd.md) - Shared filtering and analysis components
- [`docs/user_stories/transactions/review_budget_alignment.md`](../transactions/review_budget_alignment.md) - Budget variance analysis integration

### Design Considerations
- **Shared Components**: Reusable classification dropdowns and data visualization components
- **Unified Interface**: Consistent analysis patterns across budget and transaction features
- **Progressive Enhancement**: Architecture supporting future multi-budget comparisons
- **Integration Points**: Smooth navigation between classification analysis and budget alignment review

## User Story

As a budget manager, I want to analyze historical spending and budget allocations for a specific classification (category, subcategory, or payoree) so that I can make informed adjustments and reduce context switching between different budget management interfaces.

## Business Context

**Problem**: Collaborative budgeting creates friction when one person frequently switches contexts between viewing historical data, current allocations, and making budget adjustments across different categories and payorees.

**Solution**: Single-page interface that shows side-by-side historical vs budget data for one classification at a time, with inline editing capabilities to minimize navigation and cognitive load.

**Value**: Reduces time spent context switching, improves budget accuracy through historical insight, and streamlines the budget adjustment workflow.

## Acceptance Criteria

### Must Have

- [ ] **`classification_type_selection`**: User can select classification type from dropdown (Category, Subcategory, Payoree)
- [ ] **`hierarchical_category_selection`**: When "Subcategory" is selected, user must first select a category, then subcategory becomes available
- [ ] **`single_classification_focus`**: Page displays data for ONE selected classification at a time
- [ ] **`historical_vs_budget_columns`**: Side-by-side display showing 12 months of historical data (left) and 12 months of budget data (right)
- [ ] **`inline_budget_editing`**: User can click budget values to edit them directly with auto-save functionality

### Should Have

- [ ] **`budget_plan_selection`**: User can select which budget plan to display (defaults to active plan)
- [ ] **`apply_to_all_months`**: Buttons to copy a budget value to all months or specific month ranges
- [ ] **`monthly_totals_display`**: Shows monthly totals for both historical and budget columns

### Could Have

- [ ] **`multi_plan_toggle`**: Toggle to show multiple budget plans (≤3) in comparison view
- [ ] **`variance_indicators`**: Visual indicators showing significant variances between historical and budget
- [ ] **`keyboard_navigation`**: Tab/Enter navigation between editable budget fields

### Won't Have (This Iteration)

- [ ] Multi-classification comparison (multiple categories at once)
- [ ] Historical data editing
- [ ] Advanced charting/visualization
- [ ] Export functionality

## Technical Considerations

### Database Queries
- Efficient aggregation of Transaction data by classification and month
- BudgetAllocation retrieval filtered by selected classification and plan
- Consider caching for frequently accessed historical data

### UI/UX Design
- Responsive table layout with fixed left column (months) and scrollable right section
- Inline editing with visual feedback and error handling
- Progressive disclosure: simple single-plan view by default, multi-plan as option

### Integration Points
- Reuse classification dropdown components from advanced search
- Consider shared data aggregation utilities with budget alignment review
- Ensure budget editing integrates with existing BudgetAllocation model validation

## Definition of Done

- [ ] All acceptance criteria passing in ATDD tests
- [ ] Responsive design works on mobile and desktop
- [ ] Inline editing preserves data integrity with validation
- [ ] Performance acceptable with large datasets (>10K transactions)
- [ ] Integration with existing budget plan management
- [ ] User documentation updated
- [ ] Code review completed