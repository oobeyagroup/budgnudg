"""
Budget Allocation Deletion Views

These views provide the user interface for budget allocation deletion functionality,
implementing the acceptance criteria from delete_budget_allocations.md.
"""

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse
from django.views.generic import DeleteView
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.views import View
import json

from budgets.models import BudgetAllocation, BudgetPlan
from budgets.services.allocation_deletion import (
    AllocationDeletionService,
    AllocationDeletionError,
)


class AllocationDeleteConfirmView(View):
    """View for allocation deletion confirmation with impact analysis."""

    def get(self, request, allocation_id):
        """Display deletion confirmation with impact analysis."""
        allocation = get_object_or_404(BudgetAllocation, id=allocation_id)
        service = AllocationDeletionService()

        # Get confirmation data with impact analysis
        confirmation_data = service.get_deletion_confirmation_data(allocation)

        # In a real implementation, this would render a confirmation template
        # For now, return JSON response for testing/API purposes
        return JsonResponse(
            {
                "allocation_id": allocation_id,
                "confirmation_required": True,
                "confirmation_data": confirmation_data,
                "csrf_token": request.META.get("CSRF_COOKIE"),
            }
        )


class AllocationDeleteView(View):
    """View for executing allocation deletion."""

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, allocation_id):
        """Execute allocation deletion after confirmation."""
        allocation = get_object_or_404(BudgetAllocation, id=allocation_id)
        service = AllocationDeletionService()

        try:
            # Check if force deletion is requested
            force = request.POST.get("force", False) == "true"

            # Execute deletion
            result = service.delete_allocation(allocation, force=force)

            # Add success message
            messages.success(
                request,
                f"Budget allocation for {result['deleted_allocation']['payoree_name']} "
                f"(${result['deleted_allocation']['amount']}) has been successfully deleted.",
            )

            # Return JSON response with success info
            return JsonResponse(
                {
                    "success": True,
                    "message": "Allocation deleted successfully",
                    "deleted_allocation": result["deleted_allocation"],
                    "redirect_url": reverse("budgets:list"),
                }
            )

        except AllocationDeletionError as e:
            # Handle deletion errors
            messages.error(request, f"Deletion failed: {str(e)}")

            return JsonResponse(
                {
                    "success": False,
                    "error": str(e),
                    "suggestions": [
                        "Verify the allocation exists and is in an active budget plan",
                        "Check if you have permission to delete this allocation",
                        "Try refreshing the page and attempting deletion again",
                    ],
                },
                status=400,
            )

        except Exception as e:
            # Handle unexpected errors
            messages.error(request, f"An unexpected error occurred: {str(e)}")

            return JsonResponse(
                {
                    "success": False,
                    "error": "Unexpected error during deletion",
                    "suggestions": [
                        "Please try again later",
                        "Contact support if the problem persists",
                    ],
                },
                status=500,
            )


class BulkAllocationDeleteView(View):
    """View for bulk allocation deletion."""

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        """Execute bulk allocation deletion."""
        try:
            # Parse allocation IDs from request
            data = json.loads(request.body)
            allocation_ids = data.get("allocation_ids", [])
            force = data.get("force", False)

            if not allocation_ids:
                return JsonResponse(
                    {"success": False, "error": "No allocations selected for deletion"},
                    status=400,
                )

            # Get allocations to delete
            allocations = BudgetAllocation.objects.filter(id__in=allocation_ids)

            if len(allocations) != len(allocation_ids):
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Some selected allocations could not be found",
                    },
                    status=400,
                )

            # Execute bulk deletion
            service = AllocationDeletionService()
            result = service.bulk_delete_allocations(list(allocations), force=force)

            # Add success message
            messages.success(
                request,
                f"Successfully deleted {result['deleted_count']} budget allocations "
                f"totaling ${result['total_amount']}",
            )

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Bulk deletion completed: {result['deleted_count']} allocations deleted",
                    "deleted_count": result["deleted_count"],
                    "total_amount": str(result["total_amount"]),
                    "payoree_names": result["payoree_names"],
                    "redirect_url": reverse("budgets:list"),
                }
            )

        except AllocationDeletionError as e:
            messages.error(request, f"Bulk deletion failed: {str(e)}")

            return JsonResponse(
                {
                    "success": False,
                    "error": str(e),
                    "suggestions": [
                        "Check that all selected allocations are in active budget plans",
                        "Verify you have permission to delete all selected allocations",
                        "Try selecting fewer allocations at once",
                    ],
                },
                status=400,
            )

        except Exception as e:
            messages.error(request, f"Bulk deletion error: {str(e)}")

            return JsonResponse(
                {
                    "success": False,
                    "error": "Unexpected error during bulk deletion",
                    "suggestions": [
                        "Please try again with fewer selections",
                        "Contact support if the problem persists",
                    ],
                },
                status=500,
            )


class AllocationImpactAnalysisView(View):
    """View for getting deletion impact analysis without executing deletion."""

    def get(self, request, allocation_id):
        """Get impact analysis for allocation deletion."""
        allocation = get_object_or_404(BudgetAllocation, id=allocation_id)
        service = AllocationDeletionService()

        try:
            # Get impact analysis
            impact = service.analyze_deletion_impact(allocation)

            return JsonResponse(
                {
                    "allocation_id": allocation_id,
                    "impact_analysis": impact,
                }
            )

        except Exception as e:
            return JsonResponse(
                {"error": f"Error analyzing deletion impact: {str(e)}"}, status=500
            )


# Legacy Django DeleteView for form-based deletion (optional)
class AllocationDeleteFormView(DeleteView):
    """Traditional form-based deletion view for budget allocations."""

    model = BudgetAllocation
    template_name = "budgets/allocation_confirm_delete.html"
    context_object_name = "allocation"

    def get_success_url(self):
        """Redirect to budget list after successful deletion."""
        return reverse("budgets:list")

    def get_context_data(self, **kwargs):
        """Add deletion impact analysis to context."""
        context = super().get_context_data(**kwargs)

        service = AllocationDeletionService()
        context["confirmation_data"] = service.get_deletion_confirmation_data(
            self.object
        )

        return context

    def delete(self, request, *args, **kwargs):
        """Override delete to use our service and add proper messaging."""
        allocation = self.get_object()
        service = AllocationDeletionService()

        try:
            result = service.delete_allocation(allocation)

            messages.success(
                request,
                f"Budget allocation for {result['deleted_allocation']['payoree_name']} "
                f"has been successfully deleted.",
            )

            return redirect(self.get_success_url())

        except AllocationDeletionError as e:
            messages.error(request, f"Deletion failed: {str(e)}")
            return redirect("budgets:list")  # or back to confirmation page
