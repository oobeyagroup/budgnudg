"""
API views for AJAX requests in transaction management
"""
from django.http import JsonResponse
from django.views import View
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from transactions.models import Category, Transaction
from transactions.utils import trace
import json
import logging

logger = logging.getLogger(__name__)


class SubcategoriesAPIView(View):
    """API endpoint to get subcategories for a given category"""
    
    @method_decorator(trace)
    def get(self, request, category_id):
        try:
            category = get_object_or_404(Category, id=category_id, parent=None)
            subcategories = category.subcategories.all().order_by('name')
            
            data = {
                'success': True,
                'subcategories': [
                    {
                        'id': sub.id,
                        'name': sub.name
                    }
                    for sub in subcategories
                ]
            }
            return JsonResponse(data)
            
        except Exception as e:
            logger.error(f"Error loading subcategories for category {category_id}: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to load subcategories'
            }, status=500)


class TransactionSuggestionsAPIView(View):
    """API endpoint to get AI suggestions for a transaction"""
    
    @method_decorator(trace)
    def get(self, request, transaction_id):
        try:
            transaction = get_object_or_404(Transaction, id=transaction_id)
            
            # Get AI suggestions
            category_suggestion = None
            subcategory_suggestion = None
            ai_reasoning = None
            
            try:
                from transactions.categorization import categorize_transaction_with_reasoning
                
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
                logger.warning(f"Error getting AI suggestions for transaction {transaction_id}: {e}")
            
            data = {
                'success': True,
                'suggestions': {
                    'category': {
                        'id': category_suggestion.id,
                        'name': category_suggestion.name
                    } if category_suggestion else None,
                    'subcategory': {
                        'id': subcategory_suggestion.id,
                        'name': subcategory_suggestion.name
                    } if subcategory_suggestion else None,
                    'reasoning': ai_reasoning
                }
            }
            
            return JsonResponse(data)
            
        except Exception as e:
            logger.error(f"Error getting AI suggestions for transaction {transaction_id}: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get AI suggestions'
            }, status=500)


class SimilarTransactionsAPIView(View):
    """API endpoint to get similar transactions"""
    
    @method_decorator(trace)
    def get(self, request, transaction_id):
        try:
            transaction = get_object_or_404(Transaction, id=transaction_id)
            limit = int(request.GET.get('limit', 10))
            
            # Find similar transactions using fuzzy matching
            similar_transactions = []
            
            try:
                from rapidfuzz import fuzz
                from transactions.utils import normalize_description
                
                # Get other transactions for comparison
                other_transactions = Transaction.objects.exclude(id=transaction.id).select_related(
                    'category', 'subcategory', 'payoree'
                )
                
                # Find transactions with similar descriptions
                current_desc_normalized = normalize_description(transaction.description)
                for t in other_transactions:
                    similarity = fuzz.token_set_ratio(
                        current_desc_normalized,
                        normalize_description(t.description)
                    )
                    if similarity >= 70:  # 70% similarity threshold
                        similar_transactions.append({
                            'transaction': t,
                            'similarity': similarity
                        })
                
                # Sort by similarity (most similar first) and limit
                similar_transactions = sorted(
                    similar_transactions,
                    key=lambda x: x['similarity'],
                    reverse=True
                )[:limit]
                
            except ImportError:
                logger.warning("rapidfuzz not available for similar transaction matching")
            except Exception as e:
                logger.warning(f"Error finding similar transactions: {e}")
            
            data = {
                'success': True,
                'transactions': [
                    {
                        'id': item['transaction'].id,
                        'date': item['transaction'].date.strftime('%Y-%m-%d'),
                        'description': item['transaction'].description,
                        'amount': float(item['transaction'].amount),
                        'similarity': item['similarity'],
                        'category': {
                            'id': item['transaction'].category.id,
                            'name': item['transaction'].category.name
                        } if item['transaction'].category else None,
                        'subcategory': {
                            'id': item['transaction'].subcategory.id,
                            'name': item['transaction'].subcategory.name
                        } if item['transaction'].subcategory else None,
                        'payoree': {
                            'id': item['transaction'].payoree.id,
                            'name': item['transaction'].payoree.name
                        } if item['transaction'].payoree else None
                    }
                    for item in similar_transactions
                ]
            }
            
            return JsonResponse(data)
            
        except Exception as e:
            logger.error(f"Error getting similar transactions for {transaction_id}: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get similar transactions'
            }, status=500)
