# transactions/views/search.py
"""
Search and filtering views for transactions.

Implements basic search functionality that will be expanded incrementally
based on ATDD test requirements.
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from decimal import Decimal
from datetime import datetime

from transactions.models import Transaction, Category, Payoree


@login_required
def search_transactions(request):
    """
    Search and filter transactions based on various criteria.

    This view starts with basic filtering and will be expanded
    incrementally as more ATDD tests are implemented.
    """
    # Start with all transactions (no user filtering since Transaction model doesn't have user field)
    transactions = Transaction.objects.all()

    # Apply filters based on GET parameters
    filters_applied = []

    # Date range filter
    date_start = request.GET.get("start_date")  # Changed from date_start to match form
    date_end = request.GET.get("end_date")  # Changed from date_end to match form

    if date_start:
        try:
            start_date = datetime.fromisoformat(date_start).date()
            transactions = transactions.filter(date__gte=start_date)
            filters_applied.append(f"Start Date: {start_date}")
        except ValueError:
            pass  # Invalid date format, ignore

    if date_end:
        try:
            end_date = datetime.fromisoformat(date_end).date()
            transactions = transactions.filter(date__lte=end_date)
            filters_applied.append(f"End Date: {end_date}")
        except ValueError:
            pass  # Invalid date format, ignore

    # Amount range filter
    amount_min = request.GET.get("min_amount")  # Changed from amount_min to match form
    amount_max = request.GET.get("max_amount")  # Changed from amount_max to match form

    if amount_min and amount_max:
        try:
            min_amount = Decimal(amount_min)
            max_amount = Decimal(amount_max)
            # For range filtering, we want transactions between min and max
            # If both are negative: min_amount <= transaction.amount <= max_amount
            # If both are positive: -max_amount <= transaction.amount <= -min_amount
            if min_amount < 0 and max_amount < 0:
                # Both negative: filter for transactions in the range
                transactions = transactions.filter(
                    amount__gte=min_amount, amount__lte=max_amount
                )
                filters_applied.append(f"Amount Range: ${min_amount} to ${max_amount}")
            elif min_amount > 0 and max_amount > 0:
                # Both positive: convert to negative range for expenses
                transactions = transactions.filter(
                    amount__gte=-max_amount, amount__lte=-min_amount
                )
                filters_applied.append(f"Amount Range: ${min_amount} to ${max_amount}")
        except (ValueError, Decimal.InvalidOperation):
            pass
    else:
        # Handle single-sided filters
        if amount_min:
            try:
                min_amount = Decimal(amount_min)
                if min_amount < 0:
                    transactions = transactions.filter(amount__gte=min_amount)
                else:
                    transactions = transactions.filter(amount__lte=-min_amount)
                filters_applied.append(f"Min Amount: ${abs(min_amount)}")
            except (ValueError, Decimal.InvalidOperation):
                pass

        if amount_max:
            try:
                max_amount = Decimal(amount_max)
                if max_amount < 0:
                    transactions = transactions.filter(amount__lte=max_amount)
                else:
                    transactions = transactions.filter(amount__gte=-max_amount)
                filters_applied.append(f"Max Amount: ${abs(max_amount)}")
            except (ValueError, Decimal.InvalidOperation):
                pass

    # Category filter
    category_id = request.GET.get("category")
    if category_id:
        try:
            category = Category.objects.get(id=category_id)
            transactions = transactions.filter(category=category)
            filters_applied.append(f"Category: {category.name}")
        except (ValueError, Category.DoesNotExist):
            pass

    # Description keyword filter
    description = request.GET.get("description")
    if description:
        transactions = transactions.filter(description__icontains=description)
        filters_applied.append(f"Description: {description}")

    # Order by date (most recent first)
    transactions = transactions.select_related(
        "category", "payoree", "bank_account"
    ).order_by("-date")

    # Limit results to first 100 for performance (can be made configurable later)
    limited_transactions = transactions[:100]

    # Calculate summary statistics
    total_count = transactions.count()
    limited_count = len(limited_transactions)
    total_amount = sum(abs(t.amount) for t in limited_transactions)
    avg_amount = total_amount / limited_count if limited_count > 0 else 0

    context = {
        "transactions": limited_transactions,
        "total_count": total_count,  # Full count for info
        "limited_count": limited_count,  # Displayed count
        "filters_applied": filters_applied,
        "summary": {
            "total_count": total_count,
            "limited_count": limited_count,
            "total_amount": total_amount,
            "avg_amount": avg_amount,
        },
        "search_params": request.GET,
        # For form dropdowns
        "categories": Category.objects.filter(parent=None).order_by("name"),
        "payorees": Payoree.objects.order_by("name"),
    }

    return render(request, "transactions/search.html", context)
