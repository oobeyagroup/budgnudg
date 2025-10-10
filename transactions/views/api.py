"""
API views for AJAX requests in transaction management
"""

from django.http import JsonResponse
from django.views import View
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from transactions.models import (
    Category,
    Transaction,
    ExcludedSimilarTransaction,
    Payoree,
)
from transactions.utils import trace
import json
import logging

logger = logging.getLogger(__name__)


class SubcategoriesAPIView(View):
    """API endpoint to get subcategories for a given category"""

    @method_decorator(trace)
    def get(self, request, category_id):
        try:
            # Check if category exists first
            try:
                category = Category.objects.get(id=category_id, parent=None)
            except Category.DoesNotExist:
                return JsonResponse(
                    {
                        "success": False,
                        "error": f"Category with ID {category_id} not found",
                    },
                    status=404,
                )

            subcategories = category.subcategories.all().order_by("name")

            data = {
                "success": True,
                "subcategories": [
                    {"id": sub.id, "name": sub.name} for sub in subcategories
                ],
            }
            return JsonResponse(data)

        except Exception as e:
            logger.error(f"Error loading subcategories for category {category_id}: {e}")
            return JsonResponse(
                {"success": False, "error": "Failed to load subcategories"}, status=500
            )


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
                from transactions.categorization import (
                    categorize_transaction_with_reasoning,
                )

                suggested_category_name, suggested_subcategory_name, ai_reasoning = (
                    categorize_transaction_with_reasoning(
                        transaction.description, float(transaction.amount)
                    )
                )

                if suggested_category_name:
                    category_suggestion = Category.objects.filter(
                        name=suggested_category_name, parent=None
                    ).first()

                if suggested_subcategory_name:
                    subcategory_suggestion = Category.objects.filter(
                        name=suggested_subcategory_name, parent__isnull=False
                    ).first()

            except Exception as e:
                logger.warning(
                    f"Error getting AI suggestions for transaction {transaction_id}: {e}"
                )

            data = {
                "success": True,
                "suggestions": {
                    "category": (
                        {"id": category_suggestion.id, "name": category_suggestion.name}
                        if category_suggestion
                        else None
                    ),
                    "subcategory": (
                        {
                            "id": subcategory_suggestion.id,
                            "name": subcategory_suggestion.name,
                        }
                        if subcategory_suggestion
                        else None
                    ),
                    "reasoning": ai_reasoning,
                },
            }

            return JsonResponse(data)

        except Exception as e:
            logger.error(
                f"Error getting AI suggestions for transaction {transaction_id}: {e}"
            )
            return JsonResponse(
                {"success": False, "error": "Failed to get AI suggestions"}, status=500
            )


class PayoreeDefaultsAPIView(View):
    """API endpoint to get default category and subcategory for a payoree"""

    @method_decorator(trace)
    def get(self, request, payoree_id):
        try:
            payoree = get_object_or_404(Payoree, id=payoree_id)

            data = {
                "success": True,
                "payoree": {"id": payoree.id, "name": payoree.name},
                "defaults": {
                    "category": (
                        {
                            "id": payoree.default_category.id,
                            "name": payoree.default_category.name,
                        }
                        if payoree.default_category
                        else None
                    ),
                    "subcategory": (
                        {
                            "id": payoree.default_subcategory.id,
                            "name": payoree.default_subcategory.name,
                        }
                        if payoree.default_subcategory
                        else None
                    ),
                },
            }

            return JsonResponse(data)

        except Exception as e:
            logger.error(
                f"Error getting payoree defaults for payoree {payoree_id}: {e}"
            )
            return JsonResponse(
                {"success": False, "error": "Failed to get payoree defaults"},
                status=500,
            )


class SimilarTransactionsAPIView(View):
    """API endpoint to get similar transactions"""

    @method_decorator(trace)
    def get(self, request, transaction_id):
        try:
            transaction = get_object_or_404(Transaction, id=transaction_id)
            limit = int(request.GET.get("limit", 10))

            # Find similar transactions using fuzzy matching
            similar_transactions = []

            try:
                from rapidfuzz import fuzz
                from transactions.utils import normalize_description

                # Get excluded transaction IDs
                excluded_ids = set(
                    ExcludedSimilarTransaction.objects.filter(
                        source_transaction=transaction
                    ).values_list("excluded_transaction_id", flat=True)
                )

                # Get other transactions for comparison (excluding already excluded ones)
                other_transactions = Transaction.objects.exclude(
                    id__in=list(excluded_ids) + [transaction.id]
                ).select_related("category", "subcategory", "payoree")

                # Find transactions with similar descriptions
                current_desc_normalized = normalize_description(transaction.description)
                for t in other_transactions:
                    similarity = fuzz.token_set_ratio(
                        current_desc_normalized, normalize_description(t.description)
                    )
                    if similarity >= 70:  # 70% similarity threshold
                        similar_transactions.append(
                            {"transaction": t, "similarity": similarity}
                        )

                # Sort by similarity (most similar first) and limit
                similar_transactions = sorted(
                    similar_transactions, key=lambda x: x["similarity"], reverse=True
                )[:limit]

            except ImportError:
                logger.warning(
                    "rapidfuzz not available for similar transaction matching"
                )
            except Exception as e:
                logger.warning(f"Error finding similar transactions: {e}")

            data = {
                "success": True,
                "transactions": [
                    {
                        "id": item["transaction"].id,
                        "date": item["transaction"].date.strftime("%Y-%m-%d"),
                        "description": item["transaction"].description,
                        "amount": float(item["transaction"].amount),
                        "similarity": item["similarity"],
                        "category": (
                            {
                                "id": item["transaction"].category.id,
                                "name": item["transaction"].category.name,
                            }
                            if item["transaction"].category
                            else None
                        ),
                        "subcategory": (
                            {
                                "id": item["transaction"].subcategory.id,
                                "name": item["transaction"].subcategory.name,
                            }
                            if item["transaction"].subcategory
                            else None
                        ),
                        "payoree": (
                            {
                                "id": item["transaction"].payoree.id,
                                "name": item["transaction"].payoree.name,
                            }
                            if item["transaction"].payoree
                            else None
                        ),
                    }
                    for item in similar_transactions
                ],
            }

            return JsonResponse(data)

        except Exception as e:
            logger.error(
                f"Error getting similar transactions for {transaction_id}: {e}"
            )
            return JsonResponse(
                {"success": False, "error": "Failed to get similar transactions"},
                status=500,
            )


class ExcludeSimilarTransactionAPIView(View):
    """API endpoint to exclude a transaction from similar transaction suggestions"""

    @method_decorator(csrf_exempt)
    @method_decorator(trace)
    def post(self, request, transaction_id):
        try:
            transaction = get_object_or_404(Transaction, id=transaction_id)
            data = json.loads(request.body)
            excluded_transaction_id = data.get("excluded_transaction_id")

            if not excluded_transaction_id:
                return JsonResponse(
                    {"success": False, "error": "excluded_transaction_id is required"},
                    status=400,
                )

            excluded_transaction = get_object_or_404(
                Transaction, id=excluded_transaction_id
            )

            # Create or get the exclusion record
            exclusion, created = ExcludedSimilarTransaction.objects.get_or_create(
                source_transaction=transaction,
                excluded_transaction=excluded_transaction,
            )

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Transaction {excluded_transaction_id} excluded from similar suggestions",
                    "created": created,
                }
            )

        except json.JSONDecodeError:
            return JsonResponse(
                {"success": False, "error": "Invalid JSON data"}, status=400
            )
        except Exception as e:
            logger.error(f"Error excluding similar transaction: {e}")
            return JsonResponse(
                {"success": False, "error": "Failed to exclude transaction"}, status=500
            )
