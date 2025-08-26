from django import forms
from ingest.models import MappingProfile, ScannedCheck
from transactions.models import Payoree
from django.core.exceptions import ValidationError
from django.forms.widgets import ClearableFileInput

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

class CheckReviewForm(forms.Form):
    bank_account = forms.CharField(max_length=50)
    check_number = forms.CharField(max_length=20, required=False)
    date = forms.DateField(input_formats=["%Y-%m-%d", "%m/%d/%Y"], required=True)
    amount = forms.DecimalField(max_digits=12, decimal_places=2)
    payoree = forms.ModelChoiceField(queryset=Payoree.objects.all(), required=False)
    memo_text = forms.CharField(max_length=255, required=False)
    # chose existing transaction or create new
    match_txn_id = forms.IntegerField(required=False)  # hidden/radio from UI
