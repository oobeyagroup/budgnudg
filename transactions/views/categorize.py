# transactions/views/categorize.py
from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.decorators import method_decorator
from transactions.models import Transaction, Category, Payoree
from transactions.forms import TransactionForm
from transactions.utils import trace
import logging

logger = logging.getLogger(__name__)

class CategorizeTransactionView(View):
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
        ai_reasoning = None
        
        # Import here to avoid circular import
        from transactions.categorization import categorize_transaction_with_reasoning, suggest_subcategory
        
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
        except Exception as e:
            logger.warning(f"Error getting AI suggestions for transaction {pk}: {e}")

        # Find similar transactions (simplified for performance)
        similar_transactions = []
        similar_categories = []

        ctx = {
            "transaction": transaction,
            "top_level_categories": top_level_categories,
            "category_suggestion": category_suggestion,
            "subcategory_suggestion": subcategory_suggestion,
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
        
        transaction.save()
        messages.success(request, f"Transaction {transaction.id} updated successfully.")
        return redirect("transactions:transactions_list")