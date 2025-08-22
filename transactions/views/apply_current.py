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
        
        # Parse JSON data from AJAX request
        category_id = None
        subcategory_id = None
        payoree_id = None
        
        if request.content_type == 'application/json':
            try:
                import json
                data = json.loads(request.body)
                category_id = data.get('category_id')
                subcategory_id = data.get('subcategory_id')
                payoree_id = data.get('payoree_id')
                logger.info(f"Parsed JSON data: category_id={category_id}, subcategory_id={subcategory_id}, payoree_id={payoree_id}")
            except json.JSONDecodeError:
                logger.error("Invalid JSON in request body")
        else:
            logger.info(f"Request content type: {request.content_type}")
        
        # Convert empty strings to None for proper comparison
        category_id = category_id if category_id else None
        subcategory_id = subcategory_id if subcategory_id else None
        payoree_id = payoree_id if payoree_id else None
        
        logger.info(f"Final IDs: category_id={category_id}, subcategory_id={subcategory_id}, payoree_id={payoree_id}")
        
        # Get the actual objects for the values to apply
        from transactions.models import Category, Payoree
        
        apply_category = None
        apply_subcategory = None
        apply_payoree = None
        
        if category_id:
            apply_category = Category.objects.filter(id=category_id).first()
            logger.info(f"Found category: {apply_category}")
        if subcategory_id:
            apply_subcategory = Category.objects.filter(id=subcategory_id).first()
            logger.info(f"Found subcategory: {apply_subcategory}")
        if payoree_id:
            apply_payoree = Payoree.objects.filter(id=payoree_id).first()
            logger.info(f"Found payoree: {apply_payoree}")
        
        # Check if there's anything to apply
        if not apply_category and not apply_payoree:
            error_message = "No category or payoree to apply to similar transactions."
            if request.headers.get('Content-Type') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': error_message})
            messages.warning(request, error_message)
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
            
            logger.info(f"Found {len(similar_transactions)} similar transactions")
            
            # Apply form values to similar transactions
            updated_count = 0
            for t in similar_transactions:
                logger.info(f"Processing transaction {t.id}: current={t.category}/{t.subcategory}/{t.payoree}")
                modified = False
                
                # Apply category (always override - including clearing)
                if t.category != apply_category:
                    logger.info(f"Updating category from {t.category} to {apply_category}")
                    t.category = apply_category
                    modified = True
                
                # Apply subcategory (always override - including clearing)
                if t.subcategory != apply_subcategory:
                    logger.info(f"Updating subcategory from {t.subcategory} to {apply_subcategory}")
                    t.subcategory = apply_subcategory
                    modified = True
                
                # Apply payoree (always override - including clearing)
                if t.payoree != apply_payoree:
                    logger.info(f"Updating payoree from {t.payoree} to {apply_payoree}")
                    t.payoree = apply_payoree
                    modified = True
                
                if modified:
                    t.save()
                    updated_count += 1
                    logger.info(f"Saved transaction {t.id} with updates")
                else:
                    logger.info(f"No changes needed for transaction {t.id}")
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