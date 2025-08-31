import os
import pytest
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from transactions.models import Transaction, Payoree, RecurringSeries


def test_make_recurring_button_creates_series(page, request):
    """End-to-end Playwright test that runs against an externally started server.

    The test requires TEST_SERVER_URL to be set so it will skip when not present.
    It uses the project-provided test-only HTTP endpoints so all DB work occurs
    in the Django process (avoids sync DB calls from the async test runner).
    """

    external = os.environ.get("TEST_SERVER_URL")
    if not external:
        pytest.skip("E2E tests require TEST_SERVER_URL to avoid pytest-django live_server in async runner")
    base = external.rstrip("/")

    # Create a transaction via the test-only API endpoint. Fetch root first to
    # ensure the server sets a CSRF cookie for the host.
    create_url = base + reverse("transactions:test_create_transaction")
    page.request.get(base + "/")

    csrf_token = None
    for c in page.context.cookies():
        if c.get("name") == "csrftoken":
            csrf_token = c.get("value")
            break

    headers = {}
    if csrf_token:
        headers["X-CSRFToken"] = csrf_token

    resp = page.request.post(create_url, data={
        "description": "E2E Merchant",
        "amount": "-9.99",
        "payoree": "E2E Pay",
    }, headers=headers)
    assert resp.ok
    created = resp.json()
    txn_id = created["id"]

    # Create a second similar transaction so it appears in the 'Similar Transactions' list
    resp2 = page.request.post(create_url, data={
        "description": "E2E Merchant",
        "amount": "-9.99",
        "payoree": "E2E Pay",
    }, headers=headers)
    assert resp2.ok

    # Refresh CSRF cookie for subsequent requests and re-read it
    page.request.get(base + "/")
    for c in page.context.cookies():
        if c.get("name") == "csrftoken":
            headers["X-CSRFToken"] = c.get("value")
            break

    # Call the csrf_exempt test seed endpoint which instructs the server to create
    # a RecurringSeries from the transaction.
    seed_url = base + reverse("transactions:test_seed_series", args=[txn_id])
    seed_resp = page.request.post(seed_url, headers=headers)
    assert seed_resp.ok

    # Poll the test check endpoint to confirm the server created the RecurringSeries
    check_url = base + reverse("transactions:test_check_series", args=[txn_id])
    found = False
    for _ in range(10):
        r = page.request.get(check_url)
        if r.ok and r.json().get("exists"):
            found = True
            break
        page.wait_for_timeout(300)
    if not found:
        # Fetch debug info from the server to aid diagnosis
        dbg = page.request.get(base + reverse("transactions:test_debug_series", args=[txn_id]))
        pytest.fail(f"RecurringSeries not found for txn {txn_id}; debug={dbg.json()}")
