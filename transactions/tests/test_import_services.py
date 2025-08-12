import pytest
from transactions.services import import_flow as imp

def test_seed_and_parse_preview(monkeypatch):
    session = {}
    text = "Date,Description,Amount\n2025-07-11,Test,1.23\n"

    # Patch mapper used by parse_preview
    monkeypatch.setattr(
        "transactions.services.mapping.map_csv_text_to_transactions",
        lambda t, p, b: [{"date": "2025-07-11", "description": "Test", "amount": 1.23, "bank_account": b}],
    )

    imp.seed_session(session, text=text, filename="t.csv", profile="visa", bank="3607")
    rows = imp.parse_preview(session)

    assert rows and rows[0]["description"] == "Test"
    assert session[imp.SESSION["index"]] == 0

def test_apply_review_advances_index():
    session = {
        imp.SESSION["parsed"]: [{"description": "A"}, {"description": "B"}],
        imp.SESSION["index"]: 0,
    }
    imp.apply_review(session, {"description": "A*"})
    assert session[imp.SESSION["parsed"]][0]["description"] == "A*"
    assert session[imp.SESSION["index"]] == 1