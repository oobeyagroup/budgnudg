"""
Views for Budget by Classification Analysis feature.

Provides analysis interface for viewing historical spending vs budget allocations
for specific classifications (categories, subcategories, payorees).
"""

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from budgets.models import BudgetPlan, BudgetAllocation
from transactions.models import Category, Payoree, Transaction


def budget_classification_analysis(request):
    """
    Main view for budget by classification analysis.

    Displays side-by-side historical vs budget data for a selected classification.
    Supports inline editing of budget values with auto-save.
    """
    context = {
        "page_title": "Budget by Classification Analysis",
        "classification_types": [
            ("category", "Category"),
            ("subcategory", "Subcategory"),
            ("payoree", "Payoree"),
        ],
    }

    # Get filter parameters
    classification_type = request.GET.get("classification_type", "")
    category_id = request.GET.get("category_id")
    subcategory_id = request.GET.get("subcategory_id")
    payoree_id = request.GET.get("payoree_id")

    # Get available categories and payorees for dropdowns
    context["categories"] = Category.objects.filter(parent__isnull=True).order_by(
        "name"
    )
    context["payorees"] = Payoree.objects.all().order_by("name")

    # Handle hierarchical category/subcategory selection
    if classification_type == "subcategory" and category_id:
        try:
            selected_category = Category.objects.get(
                id=category_id, parent__isnull=True
            )
            context["selected_category"] = selected_category
            context["subcategories"] = selected_category.subcategories.all().order_by(
                "name"
            )
        except Category.DoesNotExist:
            pass

    context["classification_type"] = classification_type
    context["category_id"] = category_id
    context["subcategory_id"] = subcategory_id
    context["payoree_id"] = payoree_id
    context["return_to"] = request.GET.get("return")

    # If a specific classification is selected, load data
    selected_classification = None
    if classification_type == "category" and category_id:
        try:
            selected_classification = Category.objects.get(
                id=category_id, parent__isnull=True
            )
            context["selected_classification"] = selected_classification
            context = _load_classification_data(
                request, context, "category", selected_classification
            )
        except Category.DoesNotExist:
            pass

    elif classification_type == "subcategory" and subcategory_id:
        try:
            selected_classification = Category.objects.get(
                id=subcategory_id, parent__isnull=False
            )
            context["selected_classification"] = selected_classification
            context = _load_classification_data(
                request, context, "subcategory", selected_classification
            )
        except Category.DoesNotExist:
            pass

    # Handle fallback: when subcategory is selected but no subcategory_id is provided,
    # check if the selected category has no subcategories and fall back to category analysis
    elif classification_type == "subcategory" and category_id and not subcategory_id:
        try:
            selected_category = Category.objects.get(
                id=category_id, parent__isnull=True
            )
            # Check if this category has any subcategories
            if not selected_category.subcategories.exists():
                # No subcategories exist, fall back to analyzing the category itself
                context["selected_classification"] = selected_category
                context["fallback_to_category"] = (
                    True  # Flag for template to show appropriate message
                )
                context = _load_classification_data(
                    request, context, "category", selected_category
                )
        except Category.DoesNotExist:
            pass

    elif classification_type == "payoree" and payoree_id:
        try:
            selected_classification = Payoree.objects.get(id=payoree_id)
            context["selected_classification"] = selected_classification
            context = _load_classification_data(
                request, context, "payoree", selected_classification
            )
        except Payoree.DoesNotExist:
            pass

    return render(request, "budgets/classification_analysis.html", context)


def _load_classification_data(
    request, context, classification_type, classification_obj
):
    """
    Load historical and budget data for the selected classification.

    Args:
        request: HTTP request
        context: Template context dictionary
        classification_type: 'category', 'subcategory', or 'payoree'
        classification_obj: The actual Category or Payoree object

    Returns:
        Updated context dictionary with historical and budget data
    """
    # Get current date and calculate 12-month ranges
    today = date.today()

    # Historical: past 12 months
    historical_start = today - relativedelta(months=12)
    historical_months = []
    for i in range(12):
        month_date = historical_start + relativedelta(months=i)
        historical_months.append(
            {
                "date": month_date,
                "year": month_date.year,
                "month": month_date.month,
                "display": month_date.strftime("%b %Y"),
            }
        )

    # Budget: coming 12 months (including current)
    budget_months = []
    for i in range(12):
        month_date = today + relativedelta(months=i)
        budget_months.append(
            {
                "date": month_date,
                "year": month_date.year,
                "month": month_date.month,
                "display": month_date.strftime("%b %Y"),
            }
        )

    context["historical_months"] = historical_months
    context["budget_months"] = budget_months

    # Get active budget plan (or default to first available)
    active_budget_plan = BudgetPlan.objects.filter(is_active=True).first()
    if not active_budget_plan:
        active_budget_plan = BudgetPlan.objects.first()

    context["active_budget_plan"] = active_budget_plan

    # Load historical transaction data
    historical_data = {}
    if classification_type == "category":
        # Sum all transactions in this category (including subcategories)
        for month_info in historical_months:
            month_transactions = Transaction.objects.filter(
                date__year=month_info["year"],
                date__month=month_info["month"],
                category=classification_obj,
            )
            # Also include subcategory transactions
            subcategory_transactions = Transaction.objects.filter(
                date__year=month_info["year"],
                date__month=month_info["month"],
                category__parent=classification_obj,
            )

            total_amount = sum(t.amount for t in month_transactions) + sum(
                t.amount for t in subcategory_transactions
            )
            historical_data[f"{month_info['year']}-{month_info['month']:02d}"] = abs(
                total_amount
            )

    elif classification_type == "subcategory":
        for month_info in historical_months:
            month_transactions = Transaction.objects.filter(
                date__year=month_info["year"],
                date__month=month_info["month"],
                category=classification_obj,
            )
            total_amount = sum(t.amount for t in month_transactions)
            historical_data[f"{month_info['year']}-{month_info['month']:02d}"] = abs(
                total_amount
            )

    elif classification_type == "payoree":
        for month_info in historical_months:
            month_transactions = Transaction.objects.filter(
                date__year=month_info["year"],
                date__month=month_info["month"],
                payoree=classification_obj,
            )
            total_amount = sum(t.amount for t in month_transactions)
            historical_data[f"{month_info['year']}-{month_info['month']:02d}"] = abs(
                total_amount
            )

    context["historical_data"] = historical_data

    # Load budget allocation data
    budget_data = {}
    allocation_by_month = {}  # Initialize for all classification types
    if active_budget_plan:
        # Find existing allocation(s) for this classification
        total_allocation_amount = Decimal("0")
        primary_allocation = None

        if classification_type == "category":
            # In payoree-centric model, find all allocations where payoree's default_category matches
            category_allocations = BudgetAllocation.objects.filter(
                budget_plan=active_budget_plan,
                payoree__default_category=classification_obj,
            )

            # Sum all allocations for this category
            for alloc in category_allocations:
                total_allocation_amount += abs(alloc.amount)
                if not primary_allocation:
                    primary_allocation = alloc

        elif classification_type == "subcategory":
            # Find allocations for payorees whose default subcategory matches
            allocations = BudgetAllocation.objects.filter(
                budget_plan=active_budget_plan,
                payoree__default_subcategory=classification_obj,
            )
            for allocation in allocations:
                total_allocation_amount += abs(allocation.amount)
                if primary_allocation is None:
                    primary_allocation = allocation

        elif classification_type == "payoree":
            # Direct payoree allocations across all budget plans
            allocations = BudgetAllocation.objects.filter(
                payoree=classification_obj,
            )

            # Build a map of allocations by month
            allocation_by_month = {}
            for allocation in allocations:
                month_key = (
                    f"{allocation.budget_plan.year}-{allocation.budget_plan.month:02d}"
                )
                allocation_by_month[month_key] = allocation
                total_allocation_amount += abs(allocation.amount)
                if primary_allocation is None:
                    primary_allocation = allocation

            # Set budget data for specific months where allocations exist
            for month_info in budget_months:
                month_key = f"{month_info['year']}-{month_info['month']:02d}"
                if month_key in allocation_by_month:
                    budget_data[month_key] = abs(allocation_by_month[month_key].amount)

        # Store allocation IDs by month for template access
        context["allocation_by_month"] = allocation_by_month
        context["current_allocation"] = primary_allocation
        context["total_allocation_amount"] = total_allocation_amount

        # For categories/subcategories, show the same budget amount for all months
        # For payorees, we already have month-specific data from the allocation lookups above
        # TODO: Support different monthly allocations for categories/subcategories
        if (
            classification_type in ["category", "subcategory"]
            and total_allocation_amount > 0
        ):
            for month_info in budget_months:
                budget_data[f"{month_info['year']}-{month_info['month']:02d}"] = (
                    total_allocation_amount
                )

    context["budget_data"] = budget_data
    context["classification_obj"] = classification_obj

    return context


@require_http_methods(["POST"])
def update_budget_allocation(request):
    """
    AJAX endpoint for inline editing of budget allocations.

    Handles auto-save functionality when users edit budget values directly.
    """
    try:
        allocation_id = request.POST.get("allocation_id")
        new_amount = request.POST.get("amount")

        if not allocation_id or not new_amount:
            return JsonResponse({"success": False, "error": "Missing parameters"})

        allocation = BudgetAllocation.objects.get(id=allocation_id)
        allocation.amount = Decimal(new_amount)
        allocation.save()

        return JsonResponse({"success": True, "new_amount": str(allocation.amount)})

    except BudgetAllocation.DoesNotExist:
        return JsonResponse({"success": False, "error": "Allocation not found"})
    except (ValueError, InvalidOperation):
        return JsonResponse({"success": False, "error": "Invalid amount"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@require_http_methods(["POST"])
def create_budget_allocation(request):
    """
    AJAX endpoint for creating new budget allocations.

    Handles creation of budget allocations when none exist for a classification.
    """
    try:
        # Import at the top to avoid scoping issues
        from transactions.models import Category, Payoree
        from ..models import get_or_create_misc_payoree

        classification_type = request.POST.get("classification_type")
        classification_id = request.POST.get("classification_id")
        amount = request.POST.get("amount")
        month = request.POST.get("month")  # Format: YYYY-MM

        if not all([classification_type, classification_id, amount, month]):
            return JsonResponse({"success": False, "error": "Missing parameters"})

        # Parse the month (format: YYYY-MM)
        try:
            year, month_num = month.split("-")
            year = int(year)
            month_num = int(month_num)
        except (ValueError, AttributeError):
            return JsonResponse({"success": False, "error": "Invalid month format"})

        # Find or create budget plan for the specific month
        # If multiple plans exist for the same month, prefer active ones
        budget_plan = BudgetPlan.objects.filter(year=year, month=month_num).first()
        created = False

        if not budget_plan:
            budget_plan, created = BudgetPlan.objects.get_or_create(
                year=year,
                month=month_num,
                defaults={
                    "name": f"Budget Plan {year}-{month_num:02d}",
                    "is_active": False,  # Don't make it active by default
                },
            )

        if not budget_plan:
            return JsonResponse({"success": False, "error": "No budget plan available"})

        # Prepare allocation data
        allocation_data = {
            "budget_plan": budget_plan,
            "amount": Decimal(amount),
        }

        # Set classification based on type - create or get misc payorees for categories
        if classification_type == "category":
            classification_obj = Category.objects.get(id=classification_id)
            # Create or get a misc payoree for this category
            misc_payoree = get_or_create_misc_payoree(
                name_suffix=f"{classification_obj.name} - Misc",
                default_category=classification_obj,
            )
            allocation_data["payoree"] = misc_payoree

        elif classification_type == "subcategory":
            classification_obj = Category.objects.get(id=classification_id)
            # Create or get a misc payoree for this subcategory
            misc_payoree = get_or_create_misc_payoree(
                name_suffix=f"{classification_obj.name} - Misc",
                default_category=classification_obj.parent,
                default_subcategory=classification_obj,
            )
            allocation_data["payoree"] = misc_payoree

        elif classification_type == "payoree":
            classification_obj = Payoree.objects.get(id=classification_id)
            allocation_data["payoree"] = classification_obj
        else:
            return JsonResponse(
                {"success": False, "error": "Invalid classification type"}
            )

        # Check if allocation already exists
        existing = (
            BudgetAllocation.objects.filter(**allocation_data).exclude(amount=0).first()
        )
        if existing:
            return JsonResponse(
                {"success": False, "error": "Allocation already exists"}
            )

        # Create new allocation
        allocation = BudgetAllocation.objects.create(**allocation_data)

        return JsonResponse(
            {
                "success": True,
                "allocation_id": allocation.id,
                "new_amount": str(allocation.amount),
            }
        )

    except (Category.DoesNotExist, Payoree.DoesNotExist):
        return JsonResponse({"success": False, "error": "Classification not found"})
    except (ValueError, InvalidOperation):
        return JsonResponse({"success": False, "error": "Invalid amount"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})
