# Prompt Guidance for AI Development

## Code Quality Expectations

When working with AI assistants on code implementation, use these prompting patterns to set clear expectations for code quality and architectural decisions.

## Prompting Patterns

### Quick & Dirty (Prototyping)
- `"Quick prototype needed - prioritize speed over structure"`
- `"MVP approach - get it working first, optimize later"`
- `"Spike solution - expect to throw away and rebuild properly"`

### Production Quality (Default)
- `"Production-ready implementation following DRY/SOLID principles"`
- `"Implement this properly - it should be maintainable long-term"`
- `"Build this right the first time using established patterns"`

### Architectural Decisions
- `"Check for existing similar functionality before creating new code"`
- `"Prefer extending/reusing existing code over duplication"`
- `"If copying code, explain why and suggest refactoring plan"`

### Style/UI Changes
- `"Style change only - reuse existing backend logic"`
- `"New UI, same data - extend don't duplicate"`
- `"DRY principle applies - justify any code duplication"`

## The Magic Phrase ⭐

> **"Assume this will be maintained long-term unless explicitly stated otherwise"**

This single line encourages proper architectural thinking and prevents quick implementation bias.

## Example Case Study

**Poor Prompt**: "Create a glassmorphism transaction report"
- Result: Duplicated entire view logic for styling changes

**Better Prompt**: "Add glassmorphism styling to existing transaction report - reuse existing view logic, don't duplicate business logic"
- Result: Would extend existing view with template parameter

## Key Principles

1. **Default to maintainable code** unless prototyping
2. **Explicitly call out when duplication is acceptable**
3. **Ask for architectural justification** when creating new similar code
4. **Specify reuse expectations** upfront

## Notes

- AI assistants often default to "quick implementation bias"
- Being explicit about quality expectations improves code architecture
- Good engineering practices need to be requested, not assumed