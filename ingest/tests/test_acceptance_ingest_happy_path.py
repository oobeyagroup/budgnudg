# ingest/tests/test_acceptance_ingest_happy_path.py
import pytest
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from ingest.models import ImportBatch, MappingProfile
from transactions.models import Transaction, Category, Payoree

pytestmark = pytest.mark.django_db

@pytest.fixture
def profile_basic():
    return MappingProfile.objects.create(
        name="visa",
        column_map={
            "Posting Date": "date",
            "Description": "description",
            "Amount": "amount",
        },
    )

@pytest.fixture
def csv_bytes_basic():
    text = (
        "Posting Date,Description,Amount\n"
        "07/11/2025,STARBUCKS 123,-4.50\n"
        "07/12/2025,TARGET #0001,-25.00\n"
    )
    return text.encode("utf-8")

def _upload(client, csv_bytes, filename="t.csv"):
    f = SimpleUploadedFile(filename, csv_bytes, content_type="text/csv")
    return client.post(reverse("ingest:batch_upload"), {"file": f}, follow=True)

def test_upload_creates_batch_and_rows(client, csv_bytes_basic):
    resp = _upload(client, csv_bytes_basic)
    assert resp.status_code == 200
    batch = ImportBatch.objects.order_by("-id").first()
    assert batch is not None
    assert batch.status == "uploaded"
    assert batch.rows.count() == 2

def test_apply_profile_populates_parsed_normals_and_preview(client, profile_basic, csv_bytes_basic):
    _upload(client, csv_bytes_basic)
    batch = ImportBatch.objects.latest("id")

    resp = client.post(reverse("ingest:batch_apply_profile", args=[batch.id]), {"profile_id": profile_basic.id}, follow=True)
    assert resp.status_code == 200

    batch.refresh_from_db()
    assert batch.profile_id == profile_basic.id

    rows = list(batch.rows.order_by("row_index"))
    assert len(rows) == 2
    for r in rows:
        assert isinstance(r.parsed, dict)
        assert "description" in r.parsed
        assert "amount" in r.parsed
        assert r.norm_date is not None
        assert r.norm_amount is not None

    preview = client.get(reverse("ingest:batch_detail", args=[batch.id]))
    assert preview.status_code == 200
    html = preview.content.decode()
    assert "STARBUCKS" in html
    assert "TARGET" in html

def test_commit_creates_transactions_and_marks_committed(client, profile_basic, csv_bytes_basic):
    Category.objects.get_or_create(name="Coffee", parent=None)
    Payoree.objects.get_or_create(name="STARBUCKS")

    _upload(client, csv_bytes_basic)
    batch = ImportBatch.objects.latest("id")
    client.post(reverse("ingest:batch_apply_profile", args=[batch.id]), {"profile_id": profile_basic.id}, follow=True)

    resp = client.post(reverse("ingest:batch_commit", args=[batch.id]), {"bank_account": "CHK-3607"}, follow=True)
    assert resp.status_code == 200

    batch.refresh_from_db()
    assert batch.status == "committed"

    assert Transaction.objects.filter(bank_account="CHK-3607").count() == 2

def test_full_happy_path_in_one_go(client, profile_basic, csv_bytes_basic):
    up = _upload(client, csv_bytes_basic)
    assert up.status_code == 200
    batch = ImportBatch.objects.latest("id")

    client.post(reverse("ingest:batch_apply_profile", args=[batch.id]), {"profile_id": profile_basic.id}, follow=True)

    detail = client.get(reverse("ingest:batch_detail", args=[batch.id]))
    assert detail.status_code == 200

    resp = client.post(reverse("ingest:batch_commit", args=[batch.id]), {"bank_account": "CHK-3607"}, follow=True)
    assert resp.status_code == 200

    batch.refresh_from_db()
    assert batch.status == "committed"
    assert Transaction.objects.filter(bank_account="CHK-3607").count() == 2
    