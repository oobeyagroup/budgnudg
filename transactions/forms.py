from django import forms
from .models import Transaction, Category
from django.utils.decorators import method_decorator
from transactions.utils import trace
import logging

logger = logging.getLogger(__name__)


class CategoryImportForm(forms.Form):
    file = forms.FileField(
        label="Categories CSV",
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
        help_text="CSV with headers: Category, SubCategory",
    )


class PayoreeImportForm(forms.Form):
    file = forms.FileField(
        label="Payorees CSV",
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
        help_text="CSV with header: Name",
    )


class TransactionForm(forms.ModelForm):
    """Enhanced form for editing transactions with hierarchical category support."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set up category choices (top-level only)
        self.fields["category"].queryset = Category.objects.filter(
            parent=None
        ).order_by("name")
        self.fields["category"].empty_label = "-- Select Category --"

        # Set up subcategory choices based on current category
        if self.instance and self.instance.category:
            self.fields["subcategory"].queryset = Category.objects.filter(
                parent=self.instance.category
            ).order_by("name")
        else:
            self.fields["subcategory"].queryset = Category.objects.none()

        self.fields["subcategory"].empty_label = "-- No Subcategory --"

        # Add CSS classes and attributes for better styling and UX
        form_control_class = "form-control"

        self.fields["date"].widget.attrs.update(
            {"class": form_control_class, "type": "date"}
        )
        self.fields["description"].widget.attrs.update(
            {
                "class": form_control_class,
                "rows": 3,
                "placeholder": "Enter transaction description...",
            }
        )
        self.fields["amount"].widget.attrs.update(
            {"class": form_control_class, "step": "0.01", "placeholder": "0.00"}
        )
        self.fields["bank_account"].widget.attrs.update(
            {"class": form_control_class, "placeholder": "Bank or account name..."}
        )
        self.fields["payoree"].widget.attrs.update(
            {"class": form_control_class, "placeholder": "Who was paid or who paid..."}
        )
        self.fields["category"].widget.attrs.update(
            {
                "class": form_control_class,
                "id": "id_category",  # For JavaScript handling
            }
        )
        self.fields["subcategory"].widget.attrs.update(
            {
                "class": form_control_class,
                "id": "id_subcategory",  # For JavaScript handling
            }
        )
        self.fields["memo"].widget.attrs.update(
            {
                "class": form_control_class,
                "rows": 2,
                "placeholder": "Additional notes...",
            }
        )

    class Meta:
        model = Transaction
        fields = [
            "date",
            "description",
            "amount",
            "bank_account",
            "payoree",
            "category",
            "subcategory",
            "memo",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "amount": forms.NumberInput(attrs={"step": "0.01"}),
            "memo": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {
            "bank_account": "Bank Account",
            "payoree": "Payee/Payer",
            "memo": "Notes/Memo",
        }
        help_texts = {
            "description": "Brief description of the transaction",
            "amount": "Transaction amount (positive for income, negative for expenses)",
            "payoree": "The person or business involved in this transaction",
            "category": "Main category for this transaction",
            "subcategory": "Optional subcategory (depends on main category)",
            "memo": "Additional notes or details about this transaction",
        }

    def clean(self):
        """Validate that subcategory belongs to selected category."""
        cleaned_data = super().clean()
        category = cleaned_data.get("category")
        subcategory = cleaned_data.get("subcategory")

        if subcategory and category:
            if subcategory.parent != category:
                raise forms.ValidationError(
                    f"Subcategory '{subcategory.name}' does not belong to category '{category.name}'"
                )

        return cleaned_data


class FileUploadForm(forms.Form):
    file = forms.FileField()
    mapping_profile = forms.ChoiceField(choices=[])  # will set in __init__
    bank_account_choice = forms.ChoiceField(choices=[])  # existing accounts + __new__
    new_bank_account = forms.CharField(required=False)

    def __init__(self, *args, profile_choices=None, account_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        if profile_choices is not None:
            self.fields["mapping_profile"].choices = profile_choices
        if account_choices is not None:
            self.fields["bank_account_choice"].choices = account_choices


class TransactionImportForm(forms.Form):
    file = forms.FileField(label="Select file to import")
    mapping_profile = forms.ChoiceField(label="Mapping Profile")
    bank_account_choice = forms.ChoiceField(label="Bank Account")
    new_bank_account = forms.CharField(
        label="New Bank Account",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Enter new account name"}),
    )

    @method_decorator(trace)
    def __init__(self, *args, **kwargs):
        profile_choices = kwargs.pop("profile_choices", [])
        account_choices = kwargs.pop("account_choices", [])
        super().__init__(*args, **kwargs)
        self.fields["mapping_profile"].choices = profile_choices
        # Add "Other" option for new account entry
        account_choices.append(("__new__", "Other (Enter New)"))
        self.fields["bank_account_choice"].choices = account_choices

    def clean(self):
        cleaned_data = super().clean()
        account_choice = cleaned_data.get("bank_account_choice")
        new_account = cleaned_data.get("new_bank_account")

        if account_choice == "__new__":
            if not new_account:
                self.add_error(
                    "new_bank_account", "Please enter a new bank account name."
                )
            cleaned_data["bank_account"] = new_account
        else:
            cleaned_data["bank_account"] = account_choice

        return cleaned_data


class TransactionReviewForm(forms.Form):
    date = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"})
    )
    description = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    amount = forms.DecimalField(
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )
    bank_account = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    payoree = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    subcategory = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    sheet_account = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    account_type = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    check_num = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    memo = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )
