import pytest
from types import SimpleNamespace
from transactions.views.mixins import ImportSessionMixin
from transactions.services.helpers import json_safe_rows

class Dummy(ImportSessionMixin):
    pass

@pytest.mark.django_db
def test_session_roundtrip(client):
    mix = Dummy()
    req = client.get('/').wsgi_request
    # emulate session
    _ = req.session

    # save upload
    form = SimpleNamespace(cleaned_data={
        'file': SimpleNamespace(name='t.csv', read=lambda: b'Date,Description,Amount\n'),
        'mapping_profile': 'visa',
        'bank_account': '3607',
    })
    # monkeypatch read_uploaded_text so we don't depend on file IO
    from transactions.services import helpers as H
    def fake_read_uploaded_text(file):
        return ("Date,Description,Amount\n07/11/2025,Test,1.23\n", "t.csv")
    import transactions.services.helpers as helpers_mod
    helpers_mod.read_uploaded_text = fake_read_uploaded_text

    mix.save_upload_to_session(req, form)
    blob, profile, bank = mix.read_session_upload(req)
    assert "07/11/2025" in blob
    assert profile == "visa"
    assert bank == "3607"

    # parsed rows save/get
    rows = [{"date": "2025-07-11", "amount": "1.23"}]
    mix.save_parsed(req, rows)
    got = mix.get_parsed(req)
    assert got == json_safe_rows(rows)

    # current_row / apply_review
    row, idx, total = mix.current_row(req)
    assert idx == 0 and total == 1
    mix.apply_review(req, {"description": "Edited"})
    row2, idx2, total2 = mix.current_row(req)
    assert idx2 == 1  # advanced past end