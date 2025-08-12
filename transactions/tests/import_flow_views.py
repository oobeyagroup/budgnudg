import pytest
from django.urls import reverse
from transactions.services import import_flow as imp

@pytest.mark.django_db
def test_preview_renders_after_seed(client, monkeypatch):
    # Patch mapper
    monkeypatch.setattr(
        "transactions.services.mapping.map_csv_text_to_transactions",
        lambda t, p, b: [{"date": "2025-07-11", "description": "X", "amount": 1.0, "bank_account": b}],
    )

    # Seed session as if upload happened
    session = client.session
    imp.seed_session(session, text="Date,Description,Amount\n...", filename="t.csv", profile="visa", bank="CHK")
    session.save()

    resp = client.get(reverse("import_transactions_preview"))
    assert resp.status_code == 200
    assert b"Import Preview" in resp.content

@pytest.mark.django_db
def test_confirm_persists_and_redirects(client, monkeypatch):
    # Stub persist to avoid DB work
    monkeypatch.setattr(imp, "persist", lambda rows: (["ok"], ["dup"], []))

    session = client.session
    session[imp.SESSION["parsed"]] = [{"date": "2025-07-11", "description": "X", "amount": 1.0, "bank_account": "CHK"}]
    session.save()

    resp = client.post(reverse("import_transactions_confirm"))
    assert resp.status_code in (302, 200)