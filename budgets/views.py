from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView, ListView, DetailView
from django.views import View
from django.http import JsonResponse
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.db import transaction
from django.urls import reverse

from transactions.utils import trace
from .models import Budget, BudgetPeriod
from .services.baseline_calculator import BaselineCalculator
from .services.budget_wizard import BudgetWizard


class BudgetListView(ListView):
    """List all budgets."""

    model = Budget
    template_name = "budgets/budget_list.html"
    context_object_name = "budgets"
    paginate_by = 20

    def get_queryset(self):
        return Budget.objects.select_related(
            "category", "subcategory", "payoree"
        ).order_by("-year", "-month", "category__name", "subcategory__name")


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

        # Get budgets for this period
        budgets = Budget.objects.filter(
            year=period.year, month=period.month
        ).select_related("category", "subcategory", "payoree", "recurring_series")

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
    """Budget Report showing actual budget records with monthly analysis."""

    template_name = "budgets/budget_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all budget periods ordered by most recent first
        periods = BudgetPeriod.objects.all().order_by("-year", "-month")

        # Get budget data grouped by period
        budget_data = {}
        for period in periods:
            budgets = (
                Budget.objects.filter(year=period.year, month=period.month)
                .select_related("category", "subcategory", "payoree")
                .order_by("category__name", "subcategory__name", "payoree__name")
            )

            # Group budgets by category and subcategory for better organization
            categorized_budgets = {}
            for budget in budgets:
                category_name = (
                    budget.category.name if budget.category else "Uncategorized"
                )
                subcategory_name = (
                    budget.subcategory.name if budget.subcategory else "General"
                )

                # Initialize category if it doesn't exist
                if category_name not in categorized_budgets:
                    categorized_budgets[category_name] = {}

                # Initialize subcategory if it doesn't exist
                if subcategory_name not in categorized_budgets[category_name]:
                    categorized_budgets[category_name][subcategory_name] = []

                categorized_budgets[category_name][subcategory_name].append(budget)

            budget_data[period] = {
                "period": period,
                "budgets": budgets,
                "categorized_budgets": categorized_budgets,
                "total_count": budgets.count(),
            }

        context.update(
            {
                "periods": periods,
                "budget_data": budget_data,
            }
        )

        return context
