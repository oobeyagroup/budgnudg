# transactions/views/categorize.py
from django.views.generic import TemplateView
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.utils.decorators import method_decorator
from transactions.models import Transaction, Category, Payoree, ExcludedSimilarTransaction
from transactions.forms import TransactionForm
from transactions.utils import trace
import logging

logger = logging.getLogger(__name__)

class CategorizeTransactionView(TemplateView):
    template_name = "transactions/resolve_transaction.html"

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pk = kwargs.get('pk')
        transaction = get_object_or_404(Transaction, pk=pk)

        # Get all top-level categories for the form
        top_level_categories = Category.objects.filter(parent=None).prefetch_related('subcategories')
        
        # Get AI suggestions using our categorization system
        category_suggestion = None
        subcategory_suggestion = None
        payoree_suggestion = None
        ai_reasoning = None
        confidence_data = {'overall_confidence': 0.0, 'source': 'none', 'learning_count': 0}
        
        # Import here to avoid circular import
        from transactions.categorization import categorize_transaction_with_reasoning, suggest_subcategory, calculate_suggestion_confidence, suggest_payoree
        
        try:
            # Get AI category and subcategory suggestions with reasoning
            suggested_category_name, suggested_subcategory_name, ai_reasoning = categorize_transaction_with_reasoning(
                transaction.description, float(transaction.amount)
            )
            
            if suggested_category_name:
                category_suggestion = Category.objects.filter(
                    name=suggested_category_name, 
                    parent=None
                ).first()
            
            if suggested_subcategory_name:
                subcategory_suggestion = Category.objects.filter(
                    name=suggested_subcategory_name, 
                    parent__isnull=False
                ).first()
                
            # Calculate confidence scores for the suggestions
            confidence_data = calculate_suggestion_confidence(
                transaction.description,
                suggested_category_name,
                suggested_subcategory_name
            )
            
            # Get payoree suggestion
            suggested_payoree = suggest_payoree(transaction.description)
            if suggested_payoree:
                payoree_suggestion = Payoree.objects.filter(name=suggested_payoree).first()
            
        except Exception as e:
            logger.warning(f"Error getting AI suggestions for transaction {pk}: {e}")
            confidence_data = {'overall_confidence': 0.0, 'source': 'error', 'learning_count': 0}

        # Find similar transactions using fuzzy matching
        similar_transactions = []
        similar_categories = []
        
        try:
            from rapidfuzz import fuzz
            from transactions.utils import normalize_description
            
            # Get excluded transaction IDs
            excluded_ids = set(
                ExcludedSimilarTransaction.objects.filter(
                    source_transaction=transaction
                ).values_list('excluded_transaction_id', flat=True)
            )
            
            # Get other transactions for comparison (excluding already excluded ones)
            other_transactions = Transaction.objects.exclude(
                id__in=list(excluded_ids) + [transaction.id]
            ).select_related('category', 'subcategory', 'payoree')
            
            # Find transactions with similar descriptions
            current_desc_normalized = normalize_description(transaction.description)
            for t in other_transactions:
                similarity = fuzz.token_set_ratio(
                    current_desc_normalized,
                    normalize_description(t.description)
                )
                if similarity >= 70:  # 70% similarity threshold
                    similar_transactions.append(t)
            
            # Sort by similarity (most similar first) and limit to top 10
            similar_transactions = sorted(
                similar_transactions,
                key=lambda t: fuzz.token_set_ratio(
                    current_desc_normalized,
                    normalize_description(t.description)
                ),
                reverse=True
            )[:10]
            
            # Extract unique category/subcategory combinations from similar transactions
            category_combos = {}
            for t in similar_transactions:
                if t.category:
                    key = (t.category.id, t.subcategory.id if t.subcategory else None)
                    if key not in category_combos:
                        category_combos[key] = {'category': t.category, 'subcategory': t.subcategory, 'count': 0}
                    category_combos[key]['count'] += 1
            
            # Sort by frequency and convert to list
            similar_categories = sorted(
                [(combo['category'], combo['subcategory'], combo['count']) 
                 for combo in category_combos.values()],
                key=lambda x: x[2],  # Sort by count
                reverse=True
            )[:5]  # Top 5 most common patterns
            
        except ImportError:
            logger.warning("rapidfuzz not available for similar transaction matching")
        except Exception as e:
            logger.warning(f"Error finding similar transactions: {e}")

        context.update({
            "transaction": transaction,
            "top_level_categories": top_level_categories,
            "category_suggestion": category_suggestion,
            "subcategory_suggestion": subcategory_suggestion,
            "payoree_suggestion": payoree_suggestion,
            "ai_reasoning": ai_reasoning,
            "confidence_data": confidence_data,
            "similar_categories": similar_categories,
            "payoree_matches": [],  # Could add fuzzy matching here if needed
            "payorees": Payoree.objects.order_by('name'),
            "similar_transactions": similar_transactions,
        })
        return context

    @method_decorator(trace)
    def post(self, request, pk):
        transaction = get_object_or_404(Transaction, pk=pk)
        
        # Debug: Log all POST data
        logger.info(f"=== PAYOREE DEBUG for Transaction {pk} ===")
        logger.info(f"All POST data: {dict(request.POST)}")
        
        # Handle form submission
        payoree_id = request.POST.get('payoree')
        category_id = request.POST.get('category')
        subcategory_id = request.POST.get('subcategory')
        new_category_name = request.POST.get('new_category', '').strip()
        new_subcategory_name = request.POST.get('new_subcategory', '').strip()
        new_payoree_name = request.POST.get('new_payoree', '').strip()
        action = request.POST.get('action', 'save_return')  # Default to save_return
        
        logger.info(f"Payoree ID: {payoree_id}")
        logger.info(f"New Payoree Name: {new_payoree_name}")
        logger.info(f"Action: {action}")
        logger.info(f"Current payoree before: {transaction.payoree}")
        
        # Handle payoree creation/selection
        if payoree_id == '__new__' and new_payoree_name:
            # Create new payoree
            payoree, created = Payoree.objects.get_or_create(
                name=new_payoree_name
            )
            transaction.payoree = payoree
            logger.info(f"Created/found payoree: {payoree.name} (created: {created})")
            if created:
                messages.success(request, f"Created new payoree: {payoree.name}")
        elif payoree_id and payoree_id != '__new__':
            try:
                payoree = Payoree.objects.get(id=payoree_id)
                transaction.payoree = payoree
                logger.info(f"Assigned existing payoree: {payoree.name}")
            except (Payoree.DoesNotExist, ValueError) as e:
                logger.error(f"Error finding payoree {payoree_id}: {e}")
        elif payoree_id == '':
            # User selected "-- Select Payoree --" (empty value) - clear the payoree
            transaction.payoree = None
            logger.info("Cleared payoree (empty selection)")
        else:
            logger.info("No payoree assignment (either empty or invalid data)")
        
        logger.info(f"Payoree after assignment: {transaction.payoree}")
        logger.info("=======================================")
        
        # Handle category creation/selection
        if category_id == '__new__' and new_category_name:
            # Create new category
            category, created = Category.objects.get_or_create(
                name=new_category_name,
                defaults={'parent': None}
            )
            transaction.category = category
            if created:
                messages.success(request, f"Created new category: {category.name}")
        elif category_id and category_id != '__new__':
            try:
                transaction.category = Category.objects.get(id=category_id)
            except (Category.DoesNotExist, ValueError):
                pass
        
        # Handle subcategory creation/selection
        if subcategory_id == '__new__' and new_subcategory_name:
            # Create new subcategory under the selected/created category
            parent_category = None
            if category_id == '__new__' and new_category_name:
                parent_category = Category.objects.get(name=new_category_name)
            elif category_id and category_id != '__new__':
                try:
                    parent_category = Category.objects.get(id=category_id)
                except (Category.DoesNotExist, ValueError):
                    pass
            
            if parent_category:
                subcategory, created = Category.objects.get_or_create(
                    name=new_subcategory_name,
                    parent=parent_category
                )
                transaction.subcategory = subcategory
                if created:
                    messages.success(request, f"Created new subcategory: {subcategory.name}")
            else:
                messages.error(request, "Cannot create subcategory without a parent category.")
        elif subcategory_id and subcategory_id != '__new__':
            try:
                subcategory = Category.objects.get(id=subcategory_id)
                # Verify subcategory belongs to selected category
                if transaction.category and subcategory.parent_id == transaction.category.id:
                    transaction.subcategory = subcategory
                else:
                    transaction.subcategory = None
            except (Category.DoesNotExist, ValueError):
                pass
        else:
            transaction.subcategory = None
        
        # Save the transaction and log the result
        logger.info(f"About to save transaction {transaction.id}")
        logger.info(f"Final payoree: {transaction.payoree}")
        logger.info(f"Final category: {transaction.category}")
        logger.info(f"Final subcategory: {transaction.subcategory}")
        
        try:
            transaction.save()
            logger.info(f"Transaction {transaction.id} saved successfully")
            
            # Reload from database to verify save
            transaction.refresh_from_db()
            logger.info(f"After refresh - payoree: {transaction.payoree}")
            
            messages.success(request, f"Transaction {transaction.id} updated successfully.")
        except Exception as e:
            logger.error(f"Error saving transaction {transaction.id}: {e}")
            messages.error(request, f"Error saving transaction: {e}")
        
        # Handle different actions
        logger.info(f"Processing action: {action}")
        
        if action == 'save_next':
            # Find next uncategorized transaction
            next_transaction = Transaction.objects.filter(
                category__isnull=True
            ).exclude(id=transaction.id).order_by('date', 'id').first()
            
            if next_transaction:
                logger.info(f"Redirecting to next transaction: {next_transaction.id}")
                messages.info(request, f"Moving to next uncategorized transaction.")
                return redirect("transactions:categorize_transaction", pk=next_transaction.id)
            else:
                logger.info("No more uncategorized transactions found")
                messages.info(request, "No more uncategorized transactions! Returning to list.")
                return redirect("transactions:transactions_list")
                
        elif action == 'save_stay':
            # Stay on the current transaction page
            logger.info(f"Staying on current transaction: {transaction.id}")
            messages.success(request, f"Transaction {transaction.id} saved successfully.")
            return redirect("transactions:categorize_transaction", pk=transaction.id)
            
        else:  # action == 'save_return' or any other value
            # Return to transaction list
            logger.info("Returning to transaction list")
            return redirect("transactions:transactions_list")