# transactions/views/edit.py
from django.views.generic import UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from transactions.models import Transaction, Category
from transactions.forms import TransactionForm


class TransactionEditView(UpdateView):
    """
    View for editing individual transactions.
    Provides a comprehensive form for updating transaction details.
    """

    model = Transaction
    form_class = TransactionForm
    template_name = "transactions/edit_transaction.html"
    context_object_name = "transaction"

    def get_success_url(self):
        """Redirect back to the transaction list after successful edit."""
        return reverse_lazy("transactions:transactions_list")

    def get_context_data(self, **kwargs):
        """Add additional context for the template."""
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Edit Transaction - {self.object}",
                "page_description": "Update transaction details, categorization, and other information.",
            }
        )
        return context

    def form_valid(self, form):
        """Handle successful form submission."""
        response = super().form_valid(form)

        # Check if this is an AJAX request
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "success": True,
                    "message": f"Transaction updated successfully: {self.object}",
                    "redirect_url": self.get_success_url(),
                }
            )

        messages.success(
            self.request, f"Transaction updated successfully: {self.object}"
        )
        return response

    def form_invalid(self, form):
        """Handle form validation errors."""
        # Check if this is an AJAX request
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "success": False,
                    "errors": form.errors,
                    "message": "Please correct the errors below and try again.",
                },
                status=400,
            )

        messages.error(self.request, "Please correct the errors below and try again.")
        return super().form_invalid(form)


class TransactionEditAPIView(UpdateView):
    """
    AJAX API endpoint for updating transactions.
    Returns JSON responses for dynamic form updates.
    """

    model = Transaction
    form_class = TransactionForm

    def form_valid(self, form):
        """Return JSON success response."""
        self.object = form.save()
        return JsonResponse(
            {
                "success": True,
                "message": f"Transaction {self.object.id} updated successfully.",
                "transaction": {
                    "id": self.object.id,
                    "date": self.object.date.strftime("%Y-%m-%d"),
                    "description": self.object.description,
                    "amount": str(self.object.amount),
                    "category": (
                        self.object.category.name if self.object.category else None
                    ),
                    "subcategory": (
                        self.object.subcategory.name
                        if self.object.subcategory
                        else None
                    ),
                    "payoree": (
                        self.object.payoree.name if self.object.payoree else None
                    ),
                },
            }
        )

    def form_invalid(self, form):
        """Return JSON error response."""
        return JsonResponse(
            {
                "success": False,
                "errors": form.errors,
                "message": "Please correct the errors and try again.",
            },
            status=400,
        )


def get_subcategories_for_category(request):
    """
    AJAX endpoint to get subcategories for a selected category.
    Used for dynamic form updates.
    """
    category_id = request.GET.get("category_id")
    if not category_id:
        return JsonResponse({"subcategories": []})

    try:
        category = get_object_or_404(Category, id=category_id)
        subcategories = Category.objects.filter(parent=category).order_by("name")
        subcategory_data = [{"id": sub.id, "name": sub.name} for sub in subcategories]
        return JsonResponse({"subcategories": subcategory_data})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
