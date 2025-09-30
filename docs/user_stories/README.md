# User Stories Documentation

This directory contains user stories for the BudgNudg financial management system, organized by feature area.

## Directory Structure

```
user_stories/
├── budgets/          # Budget creation, management, and planning features
├── transactions/     # Transaction processing, analysis, and reporting
├── ingest/          # Data import and integration features
└── README.md        # This file with templates and guidelines
```

## User Story Template

Use this template when creating new user stories. Copy the template below and replace the placeholder content with your specific requirements.

---

```markdown
# [Feature Name]

**Status**: 🔄 [PLANNED|IN PROGRESS|NEEDS TESTS|COMPLETED]  
**Epic**: [Epic Name]  
**Priority**: [Must Have|Should Have|Could Have|Won't Have]  
**Estimated Effort**: [X points]  
**Actual Effort**: [X points] *(optional, add when completed)*  
**Target Release**: [Release Version/Date]  
**ATDD Status**: [No tests|Converting to ATDD|ATDD Complete] *(optional)*  

## Related User Stories

*Only include this section if there are related stories that should influence design decisions*

The implementation of this [feature name] should consider future integration with these related user stories, with design decisions favoring anticipated refactorings in these directions:

### [Category Name] Dependencies
- **[Story Title](relative/path/to/story.md)** - Brief description of how this relates

### [Category Name] Synergies  
- **[Story Title](relative/path/to/story.md)** - Brief description of shared components/patterns

### Design Considerations for Future Integration

**Shared Components**: [Describe reusable components to design for]

**Integration Points**: [Describe anticipated integration patterns]

**Progressive Enhancement**: [Describe extensibility considerations]

## User Story

As a **[user type]**, I want to **[capability]** so that **[benefit/outcome]**.

## Business Context

[Describe the business problem this story addresses, including:]
- Current pain points or limitations
- User workflow challenges
- Business value and impact
- How this fits into the broader product strategy

## Acceptance Criteria

### [Functional Area 1]
- [ ] 🚧 `[unique_test_id]` Given [context], when [action], then [outcome]
- [ ] 🚧 `[unique_test_id]` Given [context], when [action], then [outcome]

### [Functional Area 2]
- [ ] 🚧 `[unique_test_id]` Given [context], when [action], then [outcome]
- [ ] 🚧 `[unique_test_id]` Given [context], when [action], then [outcome]

## MoSCoW Prioritization

### Must Have 🔄
- [Core functionality that must be delivered]

### Should Have ⏳  
- [Important functionality that should be included if possible]

### Could Have 💡
- [Nice-to-have features for future enhancement]

### Won't Have (This Release) ❌
- [Features explicitly excluded from current scope]

## Technical Considerations

### Architecture Requirements
- [Key architectural decisions or constraints]
- [Performance requirements]
- [Integration requirements]

### Implementation Notes
- [Technical approach or patterns to use]
- [Dependencies on other systems/features]
- [Security or compliance considerations]

### Testing Strategy
- [Unit testing approach]
- [Integration testing needs]  
- [ATDD conversion plans if applicable]

## Definition of Done

- [ ] All acceptance criteria implemented and tested
- [ ] Unit tests written and passing
- [ ] Integration tests written and passing
- [ ] Documentation updated
- [ ] Code review completed
- [ ] UI/UX review completed (if applicable)
- [ ] Performance testing completed (if applicable)
- [ ] Security review completed (if applicable)
- [ ] Product owner acceptance obtained

## Notes

[Any additional notes, assumptions, or clarifications]
```

---

## Status Icons Guide

| Icon | Status | Description |
|------|--------|-------------|
| 🔄 | PLANNED | Story defined but not yet started |
| 🚧 | IN PROGRESS | Currently being developed |
| ⏳ | NEEDS TESTS | Implementation complete, needs ATDD tests |
| ✅ | COMPLETED | Fully implemented and tested |

## Acceptance Criteria Icons

| Icon | Status | Description |
|------|--------|-------------|
| 🚧 | In Progress | Currently being implemented |
| ⏳ | Waiting | Defined but not yet started |
| ✅ | Complete | Implemented and tested |
| 💡 | Future | Could have / future enhancement |
| ❌ | Excluded | Won't have in current release |

## ATDD Format Guidelines

When converting stories to Acceptance Test Driven Development (ATDD):

1. **Unique Test IDs**: Each acceptance criterion should have a unique identifier (e.g., `search_by_date_range`)
2. **Gherkin Format**: Use "Given [context], when [action], then [outcome]" format
3. **Test Linkage**: Link criteria to actual automated tests in the codebase
4. **Incremental Development**: Convert stories to ATDD format incrementally as they're implemented

## Example Stories

For reference examples of complete user stories, see:
- **[Advanced Transaction Search & Filtering](transactions/advanced_search_filtering.md)** - Example of comprehensive feature story
- **[Advanced Search ATDD](transactions/advanced_search_filtering_atdd.md)** - Example of ATDD format conversion
- **[Create Budget Allocations](budgets/create_budget_allocations.md)** - Example of core functionality story
- **[Review Budget Alignment](transactions/review_budget_alignment.md)** - Example with related stories section

## Writing Guidelines

### User Story Format
- Use active voice and specific user types
- Focus on user value and outcomes, not technical implementation
- Keep stories independent and testable

### Acceptance Criteria
- Write from the user's perspective
- Be specific and measurable
- Include both positive and negative test cases
- Consider edge cases and error conditions

### Business Context
- Explain the "why" behind the feature
- Connect to business goals and user needs
- Provide context for future maintainers

### Related Stories
- Only include when there are genuine integration considerations
- Focus on design decisions that should anticipate future refactoring
- Organize by logical groupings (dependencies, synergies, infrastructure)