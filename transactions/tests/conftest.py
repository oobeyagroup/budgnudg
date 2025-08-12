# transactions/tests/conftest.py
import io
import pytest
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage

@pytest.fixture
def rf():
    return RequestFactory()

@pytest.fixture
def req_with_messages(rf):
    """
    Build a Django request with session + messages attached.
    Handles multipart automatically when files are provided.
    """
    def _build(method='get', path='/', data=None, files=None, user=None):
        data = {} if data is None else dict(data)

        if method.lower() == 'post':
            if files:
                data.update(files)
                # IMPORTANT: let rf.post choose the content_type to include the boundary
                req = rf.post(path, data=data)     # no content_type kwarg
            else:
                req = rf.post(path, data=data)  # urlencoded
        else:
            req = rf.get(path, data=data)

        req.user = user or AnonymousUser()
        # Attach session and messages
        if not hasattr(req, 'session'):
            req.session = {}
        setattr(req, '_messages', FallbackStorage(req))
        return req
    return _build

@pytest.fixture
def collect_messages():
    """Extract message strings from a request after a view call."""
    def _collect(req):
        return [m.message for m in getattr(req, "_messages", [])]
    return _collect

def attach_messages(req):
    # Messages need a storage backend for unit tests
    setattr(req, 'session', req.session if hasattr(req, 'session') else {})
    messages = FallbackStorage(req)
    setattr(req, '_messages', messages)
    return req