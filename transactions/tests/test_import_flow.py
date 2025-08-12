import io
import datetime as dt
from decimal import Decimal
import pytest
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from transactions.models import Transaction

pytestmark = pytest.mark.django_db

def _file(name, text):
    return SimpleUploadedFile(name, text.encode("utf-8"), content_type="text/csv")

def test_upload_to_preview_flow(client, monkeypatch):
    # monkeypatch profile loader
    from transactions.services import mapping as M
    def fake_profiles():
        return {"visa": {"mapping": {"Date":"date","Description":"description","Amount":"amount"}}}
    monkeypatch.setattr(M, "load_mapping_profiles", fake_profiles)

    csv = "Date,Description,Amount\n07/11/2025,Hello,1.23\n"
    resp = client.post(
        reverse("import_transactions_upload"),
        data={"mapping_profile":"visa", "bank_account_choice":"__new__", "new_bank_account":"3607", "file": _file("t.csv", csv)},
    )
    assert resp.status_code == 302
    assert resp.url.endswith(reverse("import_transactions_preview"))

    # preview page renders and stores parsed rows
    resp2 = client.get(reverse("import_transactions_preview"))
    assert resp2.status_code == 200
    assert b"Import Preview" in resp2.content

def test_confirm_persists_and_skips_duplicates(client, monkeypatch):
    # profiles
    from transactions.services import mapping as M
    def fake_profiles():
        return {"visa": {"mapping": {"Date":"date","Description":"description","Amount":"amount"}}}
    monkeypatch.setattr(M, "load_mapping_profiles", fake_profiles)

    # Seed a duplicate
    Transaction.objects.create(
        date=dt.date(2025,7,11), description="Dup", amount=Decimal("1.23"), bank_account="3607"
    )

    csv = "Date,Description,Amount\n07/11/2025,Dup,1.23\n07/12/2025,New,2.00\n"
    client.post(
        reverse("import_transactions_upload"),
        data={"mapping_profile":"visa", "bank_account_choice":"__new__", "new_bank_account":"3607", "file": _file("t.csv", csv)},
    )
    client.get(reverse("import_transactions_preview"))

    resp = client.post(reverse("import_transactions_confirm"))
    assert resp.status_code in (302, 200)  # redirect to list or render list
    assert Transaction.objects.filter(description="New").exists()
    # dup didn't create a second row
    assert Transaction.objects.filter(description="Dup").count() == 1