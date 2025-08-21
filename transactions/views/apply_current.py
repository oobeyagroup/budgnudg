from django.views import View
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.contrib import messages
from transactions.models import Transaction
from transactions.utils import trace
import logging
import json

logger = logging.getLogger(__name__)

class ApplyCurrentToSimilarView(View):
    """
    Path: apply_current/<int:transaction_id>/
    Name: apply_current_to_similar
    """

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
    def post(self, request, transaction_id):
        transaction = get_object_or_404(Transaction, pk=transaction_id)
        
        # Check if transaction has anything to apply
        if not transaction.category and not transaction.payoree:
            messages.warning(request, "No category or payoree to apply to similar transactions.")
            return HttpResponseRedirect(reverse("transactions:categorize_transaction", args=[transaction_id]))
        
        try:
            from rapidfuzz import fuzz
            from transactions.utils import normalize_description
            from transactions.models import ExcludedSimilarTransaction
            
            # Find similar transactions
            other_transactions = Transaction.objects.exclude(id=transaction.id)
            current_desc_normalized = normalize_description(transaction.description)
            
            # Get excluded transaction IDs for this source transaction
            excluded_ids = ExcludedSimilarTransaction.objects.filter(
                source_transaction=transaction
            ).values_list('excluded_transaction_id', flat=True)
            
            similar_transactions = []
            for t in other_transactions:
                # Skip if this transaction has been excluded
                if t.id in excluded_ids:
                    continue
                    
                similarity = fuzz.token_set_ratio(
                    current_desc_normalized,
                    normalize_description(t.description)
                )
                if similarity >= 75:  # Lowered threshold for bulk operations
                    similar_transactions.append(t)
            
            # Apply current transaction's values to similar ones
            updated_count = 0
            for t in similar_transactions:
                modified = False
                
                # Apply category (override existing value)
                if transaction.category and t.category != transaction.category:
                    t.category = transaction.category
                    modified = True
                
                # Apply subcategory (override existing value)
                if transaction.subcategory and t.subcategory != transaction.subcategory:
                    t.subcategory = transaction.subcategory
                    modified = True
                
                # Apply payoree (override existing value)
                if transaction.payoree and t.payoree != transaction.payoree:
                    t.payoree = transaction.payoree
                    modified = True
                
                if modified:
                    t.save()
                    updated_count += 1
            
            if updated_count > 0:
                success_message = f"Updated categorization for {updated_count} similar transaction{'s' if updated_count != 1 else ''}."
                messages.success(request, success_message)
            else:
                success_message = "No similar transactions found that needed updating."
                messages.info(request, success_message)
            
            # Return JSON response for AJAX requests
            if request.headers.get('Content-Type') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'updated_count': updated_count,
                    'message': success_message
                })
                
        except ImportError:
            error_message = "Fuzzy matching not available. Cannot find similar transactions."
            messages.error(request, error_message)
            if request.headers.get('Content-Type') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': error_message
                })
        except Exception as e:
            logger.error(f"Error applying current values to similar transactions: {e}")
            error_message = "Error occurred while applying values to similar transactions."
            messages.error(request, error_message)
            if request.headers.get('Content-Type') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': error_message
                })
        
        return HttpResponseRedirect(reverse("transactions:categorize_transaction", args=[transaction_id]))

    @method_decorator(trace)
    def get(self, request, transaction_id):
        return self.post(request, transaction_id)