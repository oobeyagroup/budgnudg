from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView, ListView, DetailView
from django.views import View
from django.http import JsonResponse
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.db import transaction
from django.db.models import Q
from django.urls import reverse

from transactions.utils import trace
from ..models import BudgetPlan, BudgetAllocation, BudgetPeriod
from ..services.baseline_calculator import BaselineCalculator
from ..services.budget_wizard import BudgetWizard


class BudgetListView(ListView):
    """List all budget allocations."""

    model = BudgetAllocation
    template_name = "budgets/budget_list.html"
    context_object_name = "budgets"
    paginate_by = 20

    def get_queryset(self):
        return BudgetAllocation.objects.select_related(
            "budget_plan",
            "payoree",
            "payoree__default_category",
            "payoree__default_subcategory",
        ).order_by(
            "-budget_plan__year",
            "-budget_plan__month",
            "budget_plan__name",
            "payoree__default_category__name",
            "payoree__default_subcategory__name",
            "payoree__name",
        )


class BudgetDetailView(DetailView):
    """Detail view for a specific budget period."""

    model = BudgetPeriod
    template_name = "budgets/budget_detail.html"
    context_object_name = "period"

    def get_object(self):
        year = self.kwargs["year"]
        month = self.kwargs["month"]
        return get_object_or_404(BudgetPeriod, year=year, month=month)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        period = self.get_object()

        # Get budget allocations for this period
        budgets = BudgetAllocation.objects.filter(
            budget_plan__year=period.year, budget_plan__month=period.month
        ).select_related(
            "budget_plan", "category", "subcategory", "payoree", "recurring_series"
        )

        context["budgets"] = budgets
        return context


@method_decorator(trace, name="dispatch")
class BudgetWizardView(TemplateView):
    """Budget wizard interface for creating new budgets."""

    template_name = "budgets/wizard.html"

    @trace
    def get(self, request):
        # Initialize the budget wizard
        wizard = BudgetWizard()
        # Pre-generate draft for better UX (optional)
        wizard.generate_budget_draft(
            target_months=3, method="median", starting_year=2025, starting_month=10
        )
        return self.render_to_response({})


class BudgetWizardSimpleView(TemplateView):
    """Simple budget wizard for testing."""

    template_name = "budgets/wizard_simple.html"


@method_decorator(trace, name="dispatch")
class BudgetBaselineAPIView(View):
    """API endpoint to get baseline calculations."""

    def get(self, request):
        """Get baseline calculations with specified method."""
        method = request.GET.get("method", "median")
        target_months = int(request.GET.get("target_months", 3))

        try:
            calculator = BaselineCalculator()
            wizard = BudgetWizard(calculator)

            draft = wizard.generate_budget_draft(
                target_months=target_months, method=method
            )

            # Apply AI suggestions
            enhanced_items = wizard.apply_ai_suggestions(draft["budget_items"])

            return JsonResponse(
                {"success": True, "draft": {**draft, "budget_items": enhanced_items}}
            )

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)


@method_decorator(trace, name="dispatch")
class BudgetSuggestAPIView(View):
    """API endpoint for AI budget suggestions."""

    def post(self, request):
        """Apply AI suggestions to budget items."""
        try:
            import json

            data = json.loads(request.body)

            wizard = BudgetWizard()
            enhanced_items = wizard.apply_ai_suggestions(
                data.get("budget_items", []), data.get("adjustment_preferences", {})
            )

            return JsonResponse({"success": True, "enhanced_items": enhanced_items})

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)


@method_decorator(trace, name="dispatch")
class BudgetCommitAPIView(View):
    """API endpoint to commit budget draft."""

    def post(self, request):
        """Commit budget items to database."""
        try:
            import json
            import logging

            logger = logging.getLogger(__name__)

            data = json.loads(request.body)

            # Log the received data for debugging
            logger.info(f"Received commit data: {data}")
            logger.info(f"Budget items count: {len(data.get('budget_items', []))}")
            logger.info(f"Target periods count: {len(data.get('target_periods', []))}")

            wizard = BudgetWizard()
            result = wizard.commit_budget_draft(
                budget_items=data.get("budget_items", []),
                target_periods=data.get("target_periods", []),
                overwrite_existing=data.get("overwrite_existing", True),
            )

            logger.info(f"Commit result: {result}")

            return JsonResponse({"success": True, "result": result})

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error in commit_budget_draft: {e}")
            return JsonResponse({"success": False, "error": str(e)}, status=500)


@method_decorator(trace, name="dispatch")
class BudgetVsActualView(TemplateView):
    """Compare budgets vs actual spending."""

    template_name = "budgets/budget_vs_actual.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get recent budget periods
        periods = BudgetPeriod.objects.all()[:6]

        # For now, just pass the periods
        # TODO: Add actual vs budget comparison logic
        context["periods"] = periods

        return context


@method_decorator(trace, name="dispatch")
class BudgetReportView(TemplateView):
    """Budget Report showing actual budget records with monthly analysis - mirrors Transaction Report structure."""

    template_name = "budgets/budget_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from collections import defaultdict
        from datetime import date
        import calendar

        # For budget reports, we look FORWARD (budgets are for future months)
        # Generate list of next 12 months starting from current month
        today = date.today()

        months = []
        for i in range(12):
            # Calculate month and year going forward from current date
            year = today.year
            month = today.month + i

            # Handle year rollover
            while month > 12:
                month -= 12
                year += 1

            month_date = date(year, month, 1)
            months.append(
                {
                    "date": month_date,
                    "name": month_date.strftime("%b %Y"),
                    "short_name": month_date.strftime("%b"),
                    "year": month_date.year,
                    "month": month_date.month,
                }
            )

        # Get all budget allocations in the date range with related data
        # Use the months list to determine the exact date range to avoid KeyErrors
        month_filters = []
        for month_info in months:
            month_filters.append(
                Q(
                    budget_plan__year=month_info["year"],
                    budget_plan__month=month_info["month"],
                )
            )

        if month_filters:
            # Combine all month filters with OR
            from functools import reduce

            combined_filter = reduce(lambda q1, q2: q1 | q2, month_filters)
            budgets = (
                BudgetAllocation.objects.select_related(
                    "budget_plan",
                    "payoree__default_category",
                    "payoree__default_subcategory",
                    "payoree",
                )
                .filter(combined_filter)
                .order_by(
                    "-budget_plan__year",
                    "-budget_plan__month",
                    "budget_plan__name",
                    "payoree__default_category__name",
                    "payoree__name",
                )
            )
        else:
            budgets = BudgetAllocation.objects.none()

        # Group budgets by category type, category, and payoree
        # Consolidate all allocations for a payoree into a single row
        grouped_data = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))

        for budget in budgets:
            # Use effective category from payoree-centric model
            effective_category = budget.effective_category
            effective_subcategory = budget.effective_subcategory

            if effective_category:
                category_type = effective_category.type
                category_name = effective_category.name
                category_obj = effective_category
            else:
                category_type = "uncategorized"
                category_name = "Uncategorized"
                category_obj = None

            # Group by payoree name (consolidate all subcategories under payoree)
            payoree_name = budget.payoree.name if budget.payoree else "Unknown Payoree"
            
            # Determine month key
            month_key = f"{budget.budget_plan.year}-{budget.budget_plan.month:02d}"

            # Initialize payoree data structure if not exists
            if "payoree_obj" not in grouped_data[category_type][category_name][payoree_name]:
                grouped_data[category_type][category_name][payoree_name] = {
                    "payoree_obj": budget.payoree,
                    "category_obj": category_obj,
                    "drill_down_type": "payoree",
                    "total_amount": 0,
                    "total_count": 0,
                    "allocations": defaultdict(list),
                    "monthly_totals": defaultdict(float),
                    "monthly_sources": defaultdict(list),
                }

            # Add allocation to the payoree
            grouped_data[category_type][category_name][payoree_name]["allocations"][month_key].append(budget)
            
            # Add to monthly totals
            grouped_data[category_type][category_name][payoree_name]["monthly_totals"][month_key] += float(budget.amount)
            
            # Track source information (user vs wizard) for tooltips
            source_info = "User Created" if not budget.is_ai_suggested else "Wizard Generated"
            grouped_data[category_type][category_name][payoree_name]["monthly_sources"][month_key].append({
                "amount": float(budget.amount),
                "source": source_info,
                "note": budget.user_note if budget.user_note else None
            })
            
            # Update totals
            grouped_data[category_type][category_name][payoree_name]["total_amount"] += float(budget.amount)
            grouped_data[category_type][category_name][payoree_name]["total_count"] += 1

        # Convert to regular dict and calculate counts and monthly totals
        # Updated structure for payoree-consolidated view
        organized_data = {}
        for category_type, categories in grouped_data.items():
            organized_data[category_type] = {
                "categories": {},
                "total_count": 0,
                "total_amount": 0,
                "monthly_totals": {
                    month["date"].strftime("%Y-%m"): 0 for month in months
                },
            }

            for category_name, payorees in categories.items():
                category_data = {
                    "subcategories": {},  # Keep same structure but treat as payorees
                    "total_count": 0,
                    "total_amount": 0,
                    "category_obj": None,
                    "monthly_totals": {
                        month["date"].strftime("%Y-%m"): 0 for month in months
                    },
                }

                for payoree_name, payoree_data in payorees.items():
                    # Convert defaultdict to regular dict for template access
                    monthly_totals_dict = dict(payoree_data["monthly_totals"])
                    monthly_sources_dict = dict(payoree_data["monthly_sources"])
                    
                    # Ensure all months have entries
                    for month_info in months:
                        month_key = month_info["date"].strftime("%Y-%m")
                        if month_key not in monthly_totals_dict:
                            monthly_totals_dict[month_key] = 0
                        if month_key not in monthly_sources_dict:
                            monthly_sources_dict[month_key] = []

                    category_data["subcategories"][payoree_name] = {
                        "budgets": [{  # Consolidated payoree budget entry
                            "budget": payoree_data["payoree_obj"],  # For compatibility
                            "payoree": payoree_data["payoree_obj"],
                            "category_obj": payoree_data["category_obj"],
                            "subcategory_obj": payoree_data["payoree_obj"],
                            "drill_down_type": payoree_data["drill_down_type"],
                            "monthly_totals": monthly_totals_dict,
                            "monthly_sources": monthly_sources_dict,  # New field for tooltips
                            "total_amount": payoree_data["total_amount"],
                        }],
                        "count": payoree_data["total_count"],
                        "total_amount": payoree_data["total_amount"],
                        "monthly_totals": monthly_totals_dict,
                        "monthly_sources": monthly_sources_dict,
                        "subcategory_obj": payoree_data["payoree_obj"],
                        "drill_down_type": payoree_data["drill_down_type"],
                    }

                    # Set category object from first payoree
                    if not category_data["category_obj"]:
                        category_data["category_obj"] = payoree_data["category_obj"]

                    # Add to category totals
                    category_data["total_count"] += payoree_data["total_count"]
                    category_data["total_amount"] += payoree_data["total_amount"]
                    for month_key, amount in monthly_totals_dict.items():
                        category_data["monthly_totals"][month_key] += amount

                organized_data[category_type]["categories"][category_name] = category_data
                organized_data[category_type]["total_count"] += category_data["total_count"]
                organized_data[category_type]["total_amount"] += category_data["total_amount"]

                # Add to category type monthly totals
                for month_key, amount in category_data["monthly_totals"].items():
                    organized_data[category_type]["monthly_totals"][month_key] += amount

        # Calculate grand totals including monthly
        grand_total_count = sum(data["total_count"] for data in organized_data.values())
        grand_total_amount = sum(
            data["total_amount"] for data in organized_data.values()
        )
        grand_monthly_totals = {month["date"].strftime("%Y-%m"): 0 for month in months}

        for data in organized_data.values():
            for month_key, amount in data["monthly_totals"].items():
                if month_key in grand_monthly_totals:
                    grand_monthly_totals[month_key] += amount

        # Define category type display order (same as transaction report)
        category_type_order = [
            "income",
            "expense",
            "transfer",
            "asset",
            "liability",
            "equity",
            "uncategorized",
        ]

        # Calculate categories count
        categories_count = sum(
            len(data["categories"]) for data in organized_data.values()
        )

        # Get date range info
        start_date = months[0]["date"] if months else None
        end_date = months[-1]["date"] if months else None

        context.update(
            {
                "organized_data": organized_data,  # Transaction Report compatibility
                "category_type_order": category_type_order,
                "months": months,
                "grand_total_count": grand_total_count,
                "grand_total_amount": grand_total_amount,
                "grand_monthly_totals": grand_monthly_totals,
                "total_transactions": grand_total_count,  # Alias for budget count
                # Legacy budget report context (keeping for compatibility)
                "budget_hierarchy": organized_data,
                "categories_count": categories_count,
                "start_date": start_date,
                "end_date": end_date,
                "filter_applied": bool(
                    self.request.GET.get("category") or self.request.GET.get("search")
                ),
            }
        )

        return context


# Import allocation deletion views
from .allocation_deletion import (
    AllocationDeleteConfirmView,
    AllocationDeleteView,
    BulkAllocationDeleteView,
    AllocationImpactAnalysisView,
    AllocationDeleteFormView,
)
