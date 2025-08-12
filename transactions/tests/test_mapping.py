import datetime as dt
from decimal import Decimal
import pytest

from transactions.services import mapping as M
from transactions.services import helpers as H
from transactions.models import Transaction

@pytest.mark.django_db
def test_map_csv_applies_profile_and_flags_duplicates(monkeypatch):
    # Fake profiles
    def fake_profiles():
        return {
            "visa": {
                "mapping": {
                    "Posting Date": "date",
                    "Description": "description",
                    "Amount": "amount",
                }
            }
        }
    monkeypatch.setattr(M, "load_mapping_profiles", fake_profiles)

    # Seed an existing txn (for dup flag)
    Transaction.objects.create(
        date=dt.date(2025,7,15), description="EXISTING", amount=Decimal("47.31"), bank_account="3607"
    )

    csv_text = (
        "Posting Date,Description,Amount\n"
        "07/15/2025,EXISTING,47.31\n"
        "07/16/2025,NEW ONE,12.00\n"
    )
    rows = M.map_csv_file_to_transactions(csv_text, profile="visa", bank_account="3607")

    assert len(rows) == 2
    assert rows[0]["date"] == dt.date(2025,7,15)
    assert rows[0]["description"] == "EXISTING"
    assert rows[0]["amount"] == Decimal("47.31")
    assert rows[0]["bank_account"] == "3607"
    assert rows[0]["_is_duplicate"] is True

    assert rows[1]["description"] == "NEW ONE"
    assert rows[1]["_is_duplicate"] is False