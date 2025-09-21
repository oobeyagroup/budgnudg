# Class-Based Views (CBV) and AJAX Patterns - Design Documentation

## Overview
This document captures the critical design patterns and implementation requirements for handling AJAX requests in Django Class-Based Views within the budgnudg application.

## The Problem: CBV vs AJAX Mismatch

### Core Issue
Django Class-Based Views (CBVs) are designed for traditional browser navigation patterns (forms → redirects → new pages), but modern JavaScript frontends expect JSON responses for AJAX calls. This creates a fundamental mismatch that requires explicit handling.

### Historical Context
- **Traditional Django Pattern**: Form submission → server processing → HttpResponseRedirect → browser navigation
- **Modern AJAX Pattern**: JavaScript fetch → server processing → JsonResponse → client-side updates
- **Our Applications**: Hybrid approach needing both patterns

## Critical Implementation Requirements

### 1. AJAX Detection in CBVs
All CBVs that handle AJAX requests MUST include proper detection logic:

```python
# REQUIRED: Detect AJAX requests reliably
if request.headers.get('Content-Type') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
    # Return JSON response
    return JsonResponse({
        'success': True,
        'data': response_data,
        'message': success_message
    })
else:
    # Return traditional redirect for browser forms
    return HttpResponseRedirect(reverse('some_view'))
```

### 2. JavaScript AJAX Headers
All AJAX calls MUST include proper headers for detection:

```javascript
fetch('/some/endpoint/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        'X-Requested-With': 'XMLHttpRequest'  // CRITICAL for Django detection
    },
    body: JSON.stringify(data)
})
```

### 3. Consistent Response Patterns
All JSON responses MUST follow consistent structure:

#### Success Response
```python
return JsonResponse({
    'success': True,
    'data': result_data,           # Optional: any data to return
    'message': 'Success message',   # User-friendly message
    'updated_count': count,        # Optional: for bulk operations
})
```

#### Error Response
```python
return JsonResponse({
    'success': False,
    'error': 'Error message',      # User-friendly error
    'details': error_details,      # Optional: technical details
}, status=400)  # Appropriate HTTP status
```

## Implementation Examples

### Example 1: ApplyCurrentToSimilarView
**Problem**: JavaScript expected JSON but CBV returned HttpResponseRedirect
**Solution**: Added AJAX detection and dual response pattern

```python
class ApplyCurrentToSimilarView(View):
    def post(self, request, transaction_id):
        # ... processing logic ...
        
        try:
            # ... business logic ...
            updated_count = len(updated_transactions)
            success_message = f"Applied categorization to {updated_count} transactions"
            
            # AJAX Response
            if request.headers.get('Content-Type') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'updated_count': updated_count,
                    'message': success_message
                })
                
        except Exception as e:
            error_message = "Error occurred while processing"
            messages.error(request, error_message)
            
            # AJAX Error Response
            if request.headers.get('Content-Type') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': error_message
                })
        
        # Traditional browser response
        return HttpResponseRedirect(reverse("transactions:categorize_transaction", args=[transaction_id]))
```

### Example 2: Train AI Functionality
**Problem**: Similar AJAX/CBV mismatch in learning endpoints
**Solution**: Dedicated JSON endpoint with proper error handling

```python
class LearnFromCurrentView(View):
    def post(self, request, transaction_id):
        # ... validation and processing ...
        
        # Always return JSON for this endpoint (AJAX-only)
        try:
            # ... AI training logic ...
            return JsonResponse({
                'success': True,
                'message': 'AI training completed successfully'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': 'Training failed'
            }, status=500)
```

## Common Pitfalls and Solutions

### Pitfall 1: Missing AJAX Detection
**Problem**: CBV always returns redirects, breaking AJAX calls
**Solution**: Always implement dual response pattern for endpoints that handle both

### Pitfall 2: Inconsistent Headers
**Problem**: JavaScript doesn't set proper headers for AJAX detection
**Solution**: Standardize header inclusion in all fetch calls

### Pitfall 3: Error Handling Mismatch
**Problem**: Errors return HTML redirects instead of JSON errors
**Solution**: Wrap all error paths with AJAX detection

### Pitfall 4: CSRF Token Issues
**Problem**: AJAX calls fail due to missing CSRF protection
**Solution**: Always include CSRF token in AJAX headers

## Decision Matrix: When to Use CBV vs FBV

### Use CBV When:
- ✅ You need both AJAX and traditional form handling
- ✅ You have complex inheritance patterns
- ✅ You want Django's built-in mixins (LoginRequired, etc.)
- ✅ You have multiple HTTP methods on same endpoint

### Use FBV When:
- ✅ Simple AJAX-only endpoints
- ✅ Single-purpose API endpoints
- ✅ When you need maximum control over request handling
- ✅ Simple logic that doesn't benefit from class structure

## Testing Patterns

### Test Both Response Types
```python
def test_ajax_request(self):
    response = self.client.post('/endpoint/', 
        data=json.dumps({}),
        content_type='application/json',
        HTTP_X_REQUESTED_WITH='XMLHttpRequest'
    )
    self.assertEqual(response['Content-Type'], 'application/json')

def test_browser_request(self):
    response = self.client.post('/endpoint/', data={})
    self.assertEqual(response.status_code, 302)  # Redirect
```

## Architecture Recommendations

### 1. Consistent Patterns
- All CBVs handling AJAX MUST implement dual response pattern
- All AJAX calls MUST use standardized headers
- All JSON responses MUST follow consistent structure

### 2. Documentation Requirements
- Document AJAX capability in view docstrings
- Include example JavaScript calls in view documentation
- Note response format expectations

### 3. Code Organization
- Group AJAX-heavy views in dedicated modules
- Consider API-specific URL patterns for JSON-only endpoints
- Use mixins for common AJAX handling patterns

## Maintenance Notes

### When Adding New CBVs:
1. ✅ Determine if AJAX support is needed
2. ✅ Implement dual response pattern if needed
3. ✅ Add proper error handling for both paths
4. ✅ Document AJAX behavior
5. ✅ Test both response types

### When Debugging AJAX Issues:
1. ✅ Check request headers in Django view
2. ✅ Verify JavaScript headers are set correctly
3. ✅ Confirm response Content-Type
4. ✅ Check for CSRF token issues
5. ✅ Verify error handling paths

## Related Files
- `transactions/views/apply_current.py` - Example implementation
- `transactions/views/categorize.py` - CBV with AJAX support
- `transactions/templates/*/resolve_transaction.html` - JavaScript patterns

---
*Last Updated: August 19, 2025*
*Issue Context: "Apply Current to Similar" AJAX/CBV mismatch*
