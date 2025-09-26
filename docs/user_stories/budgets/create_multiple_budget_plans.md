# Create Multiple Budget Plans

**Status**: 🔄 IN PROGRESS  
**Epic**: Budget Management  
**Priority**: Should Have  
**Estimated Effort**: 8 points  
**Target Release**: Current Sprint  

## User Story

As a **financially flexible user**, I want to **create multiple budget scenarios (Lean, Normal, Splurge) for the same time period** so that **I can quickly switch between different spending approaches based on my current financial situation or goals**.

## Business Context

Users' financial situations change frequently:
- **Lean months**: Tight budget during low income or high expenses
- **Normal months**: Standard comfortable spending
- **Splurge months**: Extra income, bonus, or special occasions

Currently, users must manually adjust their entire budget when circumstances change. Multiple budget plans would allow pre-planned scenarios they can activate as needed.

## Acceptance Criteria

### Budget Plan Management
- [ ] 🚧 Given I want to create budget scenarios, when I access the budget planning interface, then I can create multiple named budget plans for the same time period
- [ ] 🚧 Given I have multiple budget plans, when I view my budget dashboard, then I can see all plans with their total amounts and status
- [ ] 🚧 Given I want to activate a plan, when I select "Set as Active", then that plan becomes the active budget for tracking and reporting
- [ ] 🚧 Given multiple plans exist, when I view spending reports, then I see actual spending compared to the currently active plan

### Plan Creation Workflows
- [ ] 🚧 Given I want to create a new plan, when I use the budget wizard, then I can name the plan (e.g., "Holiday Budget - Splurge") and set its scenario type
- [ ] 🚧 Given I have an existing plan, when I choose "Clone Plan", then I can create a new plan based on existing allocations with adjustable amounts
- [ ] 🚧 Given different scenario types, when I create plans, then I can apply percentage adjustments (Lean: -20%, Normal: baseline, Splurge: +30%)
- [ ] 🚧 Given I want plan templates, when I start budget creation, then I can choose from preset scenarios with typical adjustment patterns

### Plan Comparison and Analysis  
- [ ] 🚧 Given multiple budget plans for the same period, when I access comparison view, then I can see side-by-side analysis of all plans
- [ ] 🚧 Given plan comparisons, when viewing differences, then I can see variance amounts and percentages between plans by category
- [ ] 🚧 Given I want to understand plan impacts, when comparing plans, then I can see projected monthly/yearly savings differences
- [ ] 🚧 Given historical data, when viewing plans, then I can see which plan would have been most accurate for previous months

### Plan Lifecycle Management
- [ ] 🚧 Given outdated plans, when managing my budgets, then I can archive old plans while maintaining historical reference
- [ ] 🚧 Given I want to modify plans, when editing allocations, then changes only affect the selected plan, not others  
- [ ] 🚧 Given I delete a plan, when confirming deletion, then I receive appropriate warnings if it's the active plan
- [ ] 🚧 Given seasonal patterns, when creating plans, then I can set recurring activation schedules (e.g., "Lean" plan every January)

## MoSCoW Prioritization

### Must Have 🔄
- Create multiple named budget plans per time period
- Set one plan as "active" for current tracking  
- Basic plan management (create, edit, delete, activate)
- Plan comparison interface showing side-by-side allocations
- Integration with existing budget wizard and allocation system

### Should Have 🔄
- Plan cloning functionality for easy scenario creation
- Percentage-based plan adjustments (scale existing plan up/down)
- Visual indicators showing which plan is active
- Plan templates (Lean, Normal, Splurge presets)
- Archive/hide functionality for old plans

### Could Have ⏳
- Automated plan switching based on account balances or income
- Plan performance analytics (accuracy predictions vs. actual)
- Seasonal plan scheduling and activation
- Plan sharing and collaboration features
- Integration with goal-based budgeting

### Won't Have (This Release)
- ❌ Income-based dynamic plan switching
- ❌ AI-powered plan optimization recommendations  
- ❌ Plan version control and rollback
- ❌ Multi-user plan approval workflows

## Technical Implementation

### Database Schema Changes

**Current State**: ✅ Models already support multiple plans
```python
# Already implemented in current system
class BudgetPlan(models.Model):
    name = CharField()  # ✅ Supports custom names
    year = PositiveIntegerField() 
    month = PositiveSmallIntegerField()
    is_active = BooleanField()  # ✅ Supports active plan switching
    # Meta: unique_together = [("name", "year", "month")]  # ✅ Multiple plans per period

class BudgetAllocation(models.Model):
    budget_plan = ForeignKey(BudgetPlan)  # ✅ Links to specific plan
    # ... allocation details
```

### Required UI Components

**New Views Needed**:
```python
# budgets/views.py additions needed
class BudgetPlanListView(ListView):
    """Dashboard showing all budget plans with management actions"""
    
class BudgetPlanCreateView(CreateView):
    """Create new budget plan with scenario templates"""
    
class BudgetPlanCompareView(TemplateView):
    """Side-by-side comparison of multiple plans"""
    
class BudgetPlanCloneView(FormView):
    """Clone existing plan with modifications"""

# API endpoints for AJAX operations  
class BudgetPlanActivateAPI(View):
    """Set a plan as active"""
    
class BudgetPlanCloneAPI(View):
    """Clone plan with percentage adjustments"""
```

### URL Structure
```python
# budgets/urls.py additions
urlpatterns = [
    # Existing URLs...
    path("plans/", views.BudgetPlanListView.as_view(), name="plan_list"),
    path("plans/create/", views.BudgetPlanCreateView.as_view(), name="plan_create"), 
    path("plans/<int:pk>/clone/", views.BudgetPlanCloneView.as_view(), name="plan_clone"),
    path("plans/compare/", views.BudgetPlanCompareView.as_view(), name="plan_compare"),
    path("api/plans/<int:pk>/activate/", views.BudgetPlanActivateAPI.as_view(), name="api_plan_activate"),
]
```

## User Interface Mockups

### Budget Plans Dashboard
```
┌─ Budget Plans for October 2025 ────────────────────────┐
│ ┌─ Lean Budget ──────┐ ┌─ Normal Budget ─────┐ ┌─ Splurge Budget ──┐ │
│ │ $2,400/month      │ │ $3,200/month ★ ACTIVE│ │ $4,100/month      │ │
│ │ ┌─────────────────┐ │ │ ┌─────────────────┐ │ │ ┌─────────────────┐ │ │
│ │ │ View │ Edit │ Activate │ │ View │ Edit │ Compare │ │ │ │ View │ Edit │ Activate │ │ │
│ │ └─────────────────┘ │ │ └─────────────────┘ │ │ └─────────────────┘ │ │
│ └───────────────────┘ │ └───────────────────┘ │ └───────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

### Plan Comparison View
```
┌─ Budget Plan Comparison: October 2025 ─────────────────────────────┐
│                    │ Lean      │ Normal ★  │ Splurge   │ Variance │
├────────────────────┼───────────┼───────────┼───────────┼──────────┤
│ Groceries          │ $400      │ $500      │ $650      │ +30%     │
│ Utilities          │ $150      │ $200      │ $200      │ 0%       │
│ Entertainment      │ $100      │ $250      │ $500      │ +100%    │
│ Dining Out         │ $80       │ $200      │ $400      │ +100%    │
├────────────────────┼───────────┼───────────┼───────────┼──────────┤
│ TOTAL              │ $2,400    │ $3,200    │ $4,100    │ +28%     │
└────────────────────────────────────────────────────────────────────┘
```

## Testing Strategy

### Unit Tests
- [ ] 🧪 BudgetPlan model validation (unique names per period)
- [ ] 🧪 Active plan switching logic
- [ ] 🧪 Plan cloning with percentage adjustments  
- [ ] 🧪 Plan deletion with constraint checking

### Integration Tests
- [ ] 🧪 End-to-end plan creation workflow
- [ ] 🧪 Plan activation and deactivation
- [ ] 🧪 Budget wizard integration with named plans
- [ ] 🧪 Plan comparison data accuracy

### User Acceptance Tests
- [ ] 🧪 Create three budget scenarios for same month
- [ ] 🧪 Switch between plans and verify reporting changes
- [ ] 🧪 Clone and modify existing plan
- [ ] 🧪 Compare plans side-by-side

## Success Metrics

### User Adoption
- [ ] 📊 60% of users create at least 2 budget plans within first month
- [ ] 📊 40% of users actively switch between plans month-to-month
- [ ] 📊 Average 2.3 plans created per user per time period

### Feature Usage
- [ ] 📊 Plan cloning used in 80% of secondary plan creation
- [ ] 📊 Plan comparison viewed before 70% of plan activations
- [ ] 📊 Less than 5% accidental deletion of active plans

### System Performance
- [ ] 📊 Plan switching response time under 2 seconds
- [ ] 📊 Plan comparison loading under 3 seconds for 12 months of data
- [ ] 📊 No performance degradation with 10+ plans per user

## Dependencies & Blockers

### Technical Dependencies
- ✅ **BudgetPlan model architecture**: Already implemented
- ✅ **Budget allocation system**: Existing system supports multiple plans
- 🔄 **UI framework**: Need to extend existing Bootstrap templates
- 🔄 **JavaScript**: Need AJAX for plan activation without page refresh

### Business Dependencies
- 📋 **User research**: Validate assumption about budget scenario needs
- 📋 **Design review**: Ensure UI doesn't overwhelm users with choices
- 📋 **Content strategy**: Develop help text and plan templates

## Risks & Mitigation

### User Experience Risks
- **Complexity**: Multiple plans might overwhelm new users
  - *Mitigation*: Progressive disclosure, start with single plan
- **Confusion**: Users might not understand which plan is active
  - *Mitigation*: Clear visual indicators and confirmation dialogs

### Technical Risks  
- **Performance**: Many plans could slow comparison views
  - *Mitigation*: Pagination, lazy loading, database indexing
- **Data integrity**: Active plan switching could create inconsistencies
  - *Mitigation*: Database constraints, transaction wrapping

## Implementation Timeline

### Week 1-2: Foundation
- [ ] Create UI mockups and user flow designs
- [ ] Implement BudgetPlan management views (CRUD)
- [ ] Add plan activation functionality  
- [ ] Basic template structure

### Week 3-4: Core Features
- [ ] Plan comparison interface
- [ ] Plan cloning functionality
- [ ] Integration with existing budget wizard
- [ ] Plan templates and percentage adjustments

### Week 5-6: Polish & Testing
- [ ] JavaScript enhancements for smooth UX
- [ ] Comprehensive testing suite
- [ ] User acceptance testing
- [ ] Documentation and help content

## Future Enhancements

- **Smart recommendations**: Suggest which plan to activate based on account balance
- **Plan analytics**: Track which plans were most accurate over time
- **Seasonal automation**: Automatically activate different plans based on time of year
- **Goal integration**: Link plans to specific savings or spending goals