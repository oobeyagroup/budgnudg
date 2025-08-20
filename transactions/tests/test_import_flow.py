import pytest
from transactions.models import Transaction

pytestmark = pytest.mark.django_db

# TODO: Rewrite import flow tests to match current application structure
# These tests need to be rewritten from scratch to work with the current ingest app
# and transaction management system