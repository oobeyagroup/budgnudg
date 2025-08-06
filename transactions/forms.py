from django import forms
from .models import Transaction

class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['date', 'description', 'amount', 'subcategory']


class FileUploadForm(forms.Form):
    file = forms.FileField(label='Select file to import')

from django import forms

class TransactionImportForm(forms.Form):
    file = forms.FileField(label='Select file to import')
    mapping_profile = forms.ChoiceField(label='Mapping Profile')
    bank_account_choice = forms.ChoiceField(label='Bank Account')
    new_bank_account = forms.CharField(
        label='New Bank Account',
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Enter new account name'})
    )

    def __init__(self, *args, **kwargs):
        profile_choices = kwargs.pop('profile_choices', [])
        account_choices = kwargs.pop('account_choices', [])
        super().__init__(*args, **kwargs)
        self.fields['mapping_profile'].choices = profile_choices
        # Add "Other" option for new account entry
        account_choices.append(('__new__', 'Other (Enter New)'))
        self.fields['bank_account_choice'].choices = account_choices

    def clean(self):
        cleaned_data = super().clean()
        account_choice = cleaned_data.get('bank_account_choice')
        new_account = cleaned_data.get('new_bank_account')

        if account_choice == '__new__':
            if not new_account:
                self.add_error('new_bank_account', 'Please enter a new bank account name.')
            cleaned_data['bank_account'] = new_account
        else:
            cleaned_data['bank_account'] = account_choice

        return cleaned_data
    
class TransactionReviewForm(forms.Form):
    bank_account = forms.CharField()
    date = forms.DateField()
    description = forms.CharField(widget=forms.Textarea)
    amount = forms.DecimalField()
    account_type = forms.CharField(required=False)
    sheet_account = forms.CharField(required=False)
    check_num = forms.CharField(required=False)
    memo = forms.CharField(required=False)
    payoree = forms.CharField(required=False)
    subcategory = forms.CharField(required=False)