from django import forms
from ingest.models import FinancialAccount, ScannedCheck
from transactions.models import Payoree, Transaction
from django.core.exceptions import ValidationError
from django.forms.widgets import ClearableFileInput
from django.utils.decorators import method_decorator
from transactions.utils import trace


class UploadCSVForm(forms.Form):
    file = forms.FileField()
    profile = forms.ModelChoiceField(
        queryset=FinancialAccount.objects.all(), required=False
    )


# class AssignProfileForm(forms.Form):
#     profile = forms.ModelChoiceField(
#         queryset=FinancialAccount.objects.all(), required=True
#     )


class CommitForm(forms.Form):
    bank_account = forms.CharField(
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": 'Enter bank account name (e.g., "Chase Checking", "Wells Fargo Savings")',
            }
        ),
        help_text="Enter a descriptive name for the bank account these transactions belong to.",
    )


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultiFileField(forms.FileField):
    """
    Accepts one or many files. Returns a list[UploadedFile].
    """

    @method_decorator(trace)
    def to_python(self, data):
        if not data:
            return []
        if isinstance(data, (list, tuple)):
            # Coerce each element through FileField.to_python for consistency
            return [super().to_python(item) for item in data]
        # Single file -> wrap in list
        return [super().to_python(data)]

    def validate(self, data):
        # 'data' is now a list
        if self.required and not data:
            raise ValidationError("No file selected.")
        # Validate each file with base class rules (e.g., empty files)
        for f in data:
            super().validate(f)


class CheckUploadForm(forms.Form):
    images = MultiFileField(
        widget=MultiFileInput(attrs={"multiple": True}),
        required=True,
        label="Images",
        help_text="Select one or more GIF files.",
    )


class CheckReviewForm(forms.ModelForm):
    class Meta:
        model = ScannedCheck
        # include the fields you want editable in the check review screen
        fields = [
            "bank_account",
            "check_number",
            "date",
            "amount",
            "payoree",
            "memo_text",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "memo_text": forms.Textarea(attrs={"rows": 2}),
        }

    @method_decorator(trace)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optional niceties
        if "payoree" in self.fields:
            self.fields["payoree"].queryset = Payoree.objects.all().order_by("name")
            self.fields["payoree"].required = False


@trace
def bank_account_choices() -> list[tuple[str, str]]:
    qs = (
        Transaction.objects.exclude(bank_account__isnull=True)
        .values_list("bank_account__name", flat=True)
        .distinct()
        .order_by("bank_account__name")
    )
    return [(b, b) for b in qs]


class BankPickForm(forms.Form):
    bank_account = forms.ChoiceField(choices=[], required=True, label="Bank account")

    @method_decorator(trace)
    def __init__(self, *args, accounts: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bank_account"].choices = [(a, a) for a in accounts]


class AttachCheckForm(forms.Form):
    transaction_id = forms.IntegerField(widget=forms.HiddenInput())


class TransactionQuickEditForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["date", "amount", "description", "payoree", "subcategory", "memo"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "amount": forms.NumberInput(
                attrs={"step": "0.01", "class": "form-control"}
            ),
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "payoree": forms.Select(attrs={"class": "form-select"}),
            "subcategory": forms.Select(attrs={"class": "form-select"}),
            "memo": forms.TextInput(attrs={"class": "form-control"}),
        }


class AttachEditForm(forms.Form):
    transaction_id = forms.IntegerField(widget=forms.HiddenInput)
    payoree = forms.ModelChoiceField(queryset=Payoree.objects.all(), required=False)
    subcategory_id = forms.IntegerField(required=False)  # keep as int; resolve in view
    memo_text = forms.CharField(required=False, max_length=255)
    set_account_type_check = forms.BooleanField(required=False)


class CreateNewTransactionForm(forms.Form):
    date = forms.DateField(required=True)
    amount = forms.DecimalField(required=True, max_digits=12, decimal_places=2)
    description = forms.CharField(required=True, max_length=255)
    payoree = forms.ModelChoiceField(queryset=Payoree.objects.all(), required=False)
    subcategory_id = forms.IntegerField(required=False)
    bank_account = forms.CharField(required=True, max_length=64)


class CreateMappingProfileForm(forms.Form):
    """Form for creating CSV mapping profiles interactively"""

    # Basic profile information
    profile_name = forms.CharField(
        max_length=100,
        required=True,
        label="Profile Name",
        help_text="Give this mapping profile a descriptive name (e.g., 'Chase Checking CSV')",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    description = forms.CharField(
        max_length=255,
        required=False,
        label="Description",
        help_text="Optional description of what this profile is for",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )

    # Hidden field to store CSV headers
    csv_headers = forms.CharField(widget=forms.HiddenInput(), required=True)

    def __init__(self, *args, **kwargs):
        csv_headers = kwargs.pop("csv_headers", [])
        super().__init__(*args, **kwargs)

        # Set the initial value for the csv_headers hidden field
        self.fields["csv_headers"].initial = ",".join(csv_headers)

        # Transaction fields available for mapping
        TRANSACTION_FIELDS = [
            ("", "-- Skip this column --"),
            ("date", "Date"),
            ("description", "Description"),
            ("amount", "Amount"),
            ("account_type", "Account Type"),
            ("check_num", "Check Number"),
            ("payoree", "Payor/Payee"),
            ("memo", "Memo"),
            ("category", "Category"),
            ("subcategory", "Subcategory"),
            ("sheet_account", "Sheet Account"),
        ]

        # Create a dropdown for each CSV header
        for header in csv_headers:
            field_name = f"mapping_{header.replace(' ', '_').replace('-', '_')}"
            self.fields[field_name] = forms.ChoiceField(
                choices=TRANSACTION_FIELDS,
                required=False,
                label=f"Map '{header}' to:",
                widget=forms.Select(attrs={"class": "form-select mapping-dropdown"}),
            )

        # Store headers for template access
        self.csv_headers = csv_headers

        # Create mapping of headers to field names for template use
        self.header_to_field_mapping = {}
        for header in csv_headers:
            field_name = f"mapping_{header.replace(' ', '_').replace('-', '_')}"
            self.header_to_field_mapping[header] = field_name

    def get_header_field_pairs(self):
        """Return list of (header, field_name, rendered_field) tuples for template iteration"""
        pairs = []
        for header in self.csv_headers:
            field_name = self.header_to_field_mapping[header]
            field = self.fields[field_name]
            # Create a bound field to get proper attributes
            bound_field = self[field_name]
            # Render the field as HTML
            rendered_field = str(bound_field)
            pairs.append(
                (
                    header,
                    field_name,
                    rendered_field,
                    bound_field.id_for_label,
                    bound_field.errors,
                )
            )
        return pairs

    def get_mapping_dict(self):
        """Extract the column mapping from form data"""
        mapping = {}
        for field_name, field in self.fields.items():
            if field_name.startswith("mapping_") and field_name != "csv_headers":
                # Reconstruct the original CSV column name
                csv_column = field_name.replace("mapping_", "").replace("_", " ")
                transaction_field = self.cleaned_data.get(field_name)
                if transaction_field:  # Only include non-empty mappings
                    mapping[csv_column] = transaction_field
        return mapping
