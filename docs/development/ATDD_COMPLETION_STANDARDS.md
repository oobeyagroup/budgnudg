# ATDD User Story Completion Standards

## Status Definitions

### ✅ COMPLETED
- **Requirements**: 
  - All acceptance criteria have unique IDs in ATDD format: `- [ ] ✅ \`criteria_id\` Given...when...then description`
  - All criteria have corresponding automated tests with `@user_story` and `@acceptance_test` decorators
  - All linked tests are **passing** in the test suite
  - ATDD dashboard shows 100% test coverage and 100% pass rate for the story

### 🚧 IN PROGRESS
- **Requirements**:
  - Story has ATDD-format criteria IDs
  - Some automated tests exist but may be failing
  - Active development work is happening to achieve completion

### 🔄 NEEDS TESTS
- **Requirements**:
  - Story may have functional implementation
  - Acceptance criteria exist but not in ATDD format with unique IDs
  - No automated tests linked to the criteria
  - Requires ATDD conversion and test development

### 🔄 NEEDS ATDD CONVERSION
- **Requirements**:
  - Story exists in legacy format
  - Needs conversion to ATDD criteria format with unique IDs
  - May have existing tests but not linked via ATDD decorators

### ⏳ PLANNED / 💡 FUTURE
- **Requirements**:
  - Story documented but not yet implemented
  - No tests or implementation work started

## ATDD Format Requirements

### Acceptance Criteria Format
```markdown
### Category Name
- [ ] ✅ `unique_criteria_id` Given [initial state], when [action occurs], then [expected outcome]
```

### Test Annotation Format
```python
@user_story("app_name", "story_filename_without_extension")
@acceptance_test(
    name="Human Readable Test Name",
    criteria_id="unique_criteria_id",  # Must match markdown
    given="I have [initial state]",
    when="I perform [action]",
    then="the system [expected outcome]"
)
def test_descriptive_name():
    # Test implementation
    pass
```

## Validation Process

1. **Run ATDD Dashboard**: `./v --atdd` or `python manage.py generate_atdd_dashboard --generate-only`
2. **Check Coverage**: Verify all criteria have linked tests
3. **Check Pass Rate**: Ensure 100% of linked tests are passing
4. **Update Status**: Only mark ✅ COMPLETED when dashboard shows full coverage and passing tests

## Current Status Summary

| Story | Status | Tests | Coverage | Action Required |
|-------|--------|-------|----------|-----------------|
| `import_csv_transactions_atdd` | 🚧 IN PROGRESS | 9/11 passing | 100% | Fix 2 failing tests |
| `create_budget_allocations` | 🔄 NEEDS TESTS | 0/0 | 0% | Add ATDD format + tests |
| `assign_payoree` | 🔄 NEEDS TESTS | 0/0 | 0% | Add ATDD format + tests |

## Benefits of This Standard

- **Traceability**: Direct link between requirements and automated verification
- **Living Documentation**: Dashboard shows real-time implementation status
- **Quality Assurance**: No feature marked complete without automated proof
- **Team Alignment**: Clear, objective criteria for "done"
- **Regression Prevention**: Automated tests catch regressions immediately