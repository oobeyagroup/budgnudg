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
        
        # Import here to avoid circular import
        from transactions.categorization import categorize_transaction, suggest_subcategory
        
        try:
            # Get AI category suggestion
            suggested_category_name = categorize_transaction(transaction.description, float(transaction.amount))
            if suggested_category_name:
                category_suggestion = Category.objects.filter(
                    name=suggested_category_name, 
                    parent=None
                ).first()
            
            # Get AI subcategory suggestion  
            suggested_subcategory_name = suggest_subcategory(transaction.description, float(transaction.amount))
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
            "similar_categories": similar_categories,
            "payoree_matches": [],  # Could add fuzzy matching here if needed
            "payorees": Payoree.objects.order_by('name'),
            "similar_transactions": similar_transactions,
        }
        return render(request, self.template_name, ctx)

    @method_decorator(trace)
    def post(self, request, pk):
        transaction = get_object_or_404(Transaction, pk=pk)
        
        # Handle form submission similar to resolve_transaction
        payoree_id = request.POST.get('payoree')
        category_id = request.POST.get('category')
        subcategory_id = request.POST.get('subcategory')
        
        if payoree_id:
            transaction.payoree = Payoree.objects.get(id=payoree_id)
        
        if category_id:
            transaction.category = Category.objects.get(id=category_id)
            # Clear subcategory if new category is selected
            if subcategory_id:
                subcategory = Category.objects.get(id=subcategory_id)
                # Verify subcategory belongs to selected category
                if subcategory.parent_id == int(category_id):
                    transaction.subcategory = subcategory
                else:
                    transaction.subcategory = None
            else:
                transaction.subcategory = None
        
        transaction.save()
        messages.success(request, f"Transaction {transaction.id} updated successfully.")
        return redirect("transactions_list")