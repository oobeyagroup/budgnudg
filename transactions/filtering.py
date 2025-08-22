# transactions/filtering.py
from django.db.models import Q
from .models import Transaction


def apply_transaction_filters(queryset, request):
    """
    Apply transaction list filters based on request GET parameters.
    This logic is shared between TransactionListView and CategorizeTransactionView.
    
    Args:
        queryset: Base Transaction queryset to filter
        request: HTTP request object containing GET parameters
    
    Returns:
        Filtered Transaction queryset
    """
    # Filter by account
    account = request.GET.get("account")
    if account:
        queryset = queryset.filter(bank_account=account)

    # Filter for uncategorized transactions (missing payoree)
    if request.GET.get("uncategorized") == "1":
        queryset = queryset.filter(Q(payoree__isnull=True) | Q(payoree__name=""))

    # Filter for transactions without category
    if request.GET.get("no_category") == "1":
        queryset = queryset.filter(Q(category__isnull=True))

    # Filter for transactions without payoree
    if request.GET.get("no_payoree") == "1":
        queryset = queryset.filter(Q(payoree__isnull=True) | Q(payoree__name=""))

    # Search in description
    q = request.GET.get("q")
    if q:
        queryset = queryset.filter(description__icontains=q.strip())

    # Apply ordering override
    order = request.GET.get("order")
    if order:
        queryset = queryset.order_by(order)
    else:
        queryset = queryset.order_by("-date")  # Default ordering

    return queryset


def get_filtered_transaction_queryset(request):
    """
    Get a filtered Transaction queryset based on request parameters.
    This is the main entry point for getting filtered transactions.
    
    Args:
        request: HTTP request object containing GET parameters
    
    Returns:
        Filtered Transaction queryset with related objects pre-fetched
    """
    base_queryset = Transaction.objects.select_related("category", "subcategory", "payoree").all()
    return apply_transaction_filters(base_queryset, request)
