from django import forms
from ingest.models import MappingProfile, ScannedCheck
from transactions.models import Payoree, Transaction
from django.core.exceptions import ValidationError
from django.forms.widgets import ClearableFileInput

from transactions.models import Transaction


class UploadCSVForm(forms.Form):
    file = forms.FileField()
    profile = forms.ModelChoiceField(queryset=MappingProfile.objects.all(), required=False)

class AssignProfileForm(forms.Form):
    profile = forms.ModelChoiceField(queryset=MappingProfile.objects.all(), required=True)

class CommitForm(forms.Form):
    bank_account = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter bank account name (e.g., "Chase Checking", "Wells Fargo Savings")'
        }),
        help_text="Enter a descriptive name for the bank account these transactions belong to."
    )

class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultiFileField(forms.FileField):
    """
    Accepts one or many files. Returns a list[UploadedFile].
    """
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
        fields = ["bank_account", "check_number", "date", "amount", "payoree", "memo_text"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "memo_text": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optional niceties
        if "payoree" in self.fields:
            self.fields["payoree"].queryset = Payoree.objects.all().order_by("name")
            self.fields["payoree"].required = False
            
def bank_account_choices() -> list[tuple[str, str]]:
    qs = (
        Transaction.objects.exclude(bank_account__isnull=True)
        .exclude(bank_account__exact="")
        .values_list("bank_account", flat=True)
        .distinct()
        .order_by("bank_account")
    )
    return [(b, b) for b in qs]

class BankPickForm(forms.Form):
    bank_account = forms.ChoiceField(choices=[], label="Bank account")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bank_account"].choices = bank_account_choices()

class AttachCheckForm(forms.Form):
    transaction_id = forms.IntegerField(widget=forms.HiddenInput())


class TransactionQuickEditForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["date", "amount", "description", "payoree", "subcategory", "memo"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "amount": forms.NumberInput(attrs={"step": "0.01", "class": "form-control"}),
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "payoree": forms.Select(attrs={"class": "form-select"}),
            "subcategory": forms.Select(attrs={"class": "form-select"}),
            "memo": forms.TextInput(attrs={"class": "form-control"}),
        }
