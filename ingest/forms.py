from django import forms
from ingest.models import MappingProfile

class UploadCSVForm(forms.Form):
    file = forms.FileField()
    profile = forms.ModelChoiceField(queryset=MappingProfile.objects.all(), required=False)

class AssignProfileForm(forms.Form):
    profile = forms.ModelChoiceField(queryset=MappingProfile.objects.all(), required=True)

class CommitForm(forms.Form):
    bank_account = forms.CharField()