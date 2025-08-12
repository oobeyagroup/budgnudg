import pytest
from transactions.forms import FileUploadForm, TransactionImportForm, TransactionReviewForm

def test_file_upload_form_requires_file():
    f = FileUploadForm(data={}, files={})
    assert not f.is_valid()
    assert 'file' in f.errors

from django.core.files.uploadedfile import SimpleUploadedFile
from transactions.forms import TransactionImportForm

def test_transaction_import_form_new_bank_account():
    choices = [('__new__', 'New…'), ('CHK', 'CHK')]
    f = TransactionImportForm(
        data={
            'mapping_profile': 'visa',
            'bank_account_choice': '__new__',
            'new_bank_account': '3607',
        },
        files={'file': SimpleUploadedFile('t.csv', b'Date,Description,Amount\n')},
        profile_choices=[('visa', 'visa')],
        account_choices=choices,
    )
    assert f.is_valid()
    assert f.cleaned_data['bank_account'] == '3607'

def test_transaction_import_form_existing_bank_account():
    choices = [('__new__', 'New…'), ('CHK', 'CHK')]
    f = TransactionImportForm(
        data={'mapping_profile': 'visa', 'bank_account_choice': 'CHK', 'new_bank_account': ''},
        files={'file': SimpleUploadedFile('t.csv', b'Date,Description,Amount\n')},
        profile_choices=[('visa','visa')], account_choices=choices
    )
    assert f.is_valid()
    assert f.cleaned_data['bank_account'] == 'CHK'

def test_transaction_review_form_basic_fields():
    f = TransactionReviewForm(data={
        'date': '2025-07-11',
        'description': 'Hello',
        'amount': '12.34',
        'bank_account': '3607',
        'subcategory': '',
        'payoree': '',
        'memo': '',
    })
    assert f.is_valid()