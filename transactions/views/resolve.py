from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.decorators import method_decorator
from transactions.models import Transaction, Category, Payoree
from transactions.utils import trace
import logging

logger = logging.getLogger(__name__)

class ResolveTransactionView(View):
    template_name = "transactions/resolve_transaction.html"

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
    def get(self, request, pk):
        transaction = get_object_or_404(Transaction, pk=pk)

        # Get all top-level categories for the form
        top_level_categories = Category.objects.filter(parent=None).prefetch_related('subcategories')
        
        # Get AI suggestions using our categorization system
        category_suggestion = None
        subcategory_suggestion = None
        payoree_suggestion = None
        ai_reasoning = None
        
        # Import here to avoid circular import
        try:
            from transactions.categorization import categorize_transaction_with_reasoning, suggest_payoree
            
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
            
            # Get payoree suggestion
            suggested_payoree_name = suggest_payoree(transaction.description)
            if suggested_payoree_name:
                payoree_suggestion = Payoree.objects.filter(name=suggested_payoree_name).first()
                
        except Exception as e:
            logger.warning(f"Error getting AI suggestions for transaction {pk}: {e}")

        # Find similar transactions using fuzzy matching
        similar_transactions = []
        similar_categories = []
        
        try:
            from rapidfuzz import fuzz
            from transactions.utils import normalize_description
            
            # Get other transactions for comparison
            other_transactions = Transaction.objects.exclude(id=transaction.id).select_related('category', 'subcategory', 'payoree')
            
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

        ctx = {
            "transaction": transaction,
            "top_level_categories": top_level_categories,
            "category_suggestion": category_suggestion,
            "subcategory_suggestion": subcategory_suggestion,
            "payoree_suggestion": payoree_suggestion,
            "ai_reasoning": ai_reasoning,
            "similar_categories": similar_categories,
            "payoree_matches": [],  # Could add fuzzy matching here if needed
            "payorees": Payoree.objects.order_by('name'),
            "similar_transactions": similar_transactions,
        }
        return render(request, self.template_name, ctx)

    @method_decorator(trace)
    def post(self, request, pk):
        transaction = get_object_or_404(Transaction, pk=pk)
        
        # Handle form submission
        payoree_id = request.POST.get('payoree')
        category_id = request.POST.get('category')
        subcategory_id = request.POST.get('subcategory')
        new_category_name = request.POST.get('new_category', '').strip()
        new_subcategory_name = request.POST.get('new_subcategory', '').strip()
        
        if payoree_id:
            transaction.payoree = Payoree.objects.get(id=payoree_id)
        
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
            elif category_id:
                try:
                    parent_category = Category.objects.get(id=category_id)
                except Category.DoesNotExist:
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
        
        transaction.save()
        messages.success(request, f"Transaction {transaction.description} updated successfully.")
        return redirect("transactions:transactions_list")  # Fixed: add namespace