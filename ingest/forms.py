from django import forms
from ingest.models import MappingProfile

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