from django.views import View
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.contrib import messages
from transactions.models import Transaction
from transactions.utils import trace
import logging

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
            return HttpResponseRedirect(reverse("transactions:resolve_transaction", args=[transaction_id]))
        
        try:
            from rapidfuzz import fuzz
            from transactions.legacy_views import normalize_description
            
            # Find similar transactions
            other_transactions = Transaction.objects.exclude(id=transaction.id)
            current_desc_normalized = normalize_description(transaction.description)
            
            similar_transactions = []
            for t in other_transactions:
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
                
                # Apply category if transaction doesn't have one
                if transaction.category and not t.category:
                    t.category = transaction.category
                    modified = True
                
                # Apply subcategory if transaction doesn't have one
                if transaction.subcategory and not t.subcategory:
                    t.subcategory = transaction.subcategory
                    modified = True
                
                # Apply payoree if transaction doesn't have one
                if transaction.payoree and not t.payoree:
                    t.payoree = transaction.payoree
                    modified = True
                
                if modified:
                    t.save()
                    updated_count += 1
            
            if updated_count > 0:
                messages.success(
                    request, 
                    f"Applied current categorization to {updated_count} similar transaction{'s' if updated_count != 1 else ''}."
                )
            else:
                messages.info(request, "No similar transactions found that needed updating.")
                
        except ImportError:
            messages.error(request, "Fuzzy matching not available. Cannot find similar transactions.")
        except Exception as e:
            logger.error(f"Error applying current values to similar transactions: {e}")
            messages.error(request, "Error occurred while applying values to similar transactions.")
        
        return HttpResponseRedirect(reverse("transactions:resolve_transaction", args=[transaction_id]))

    @method_decorator(trace)
    def get(self, request, transaction_id):
        return self.post(request, transaction_id)