"""
Shared pytest fixtures for MyEstateAlly test suite.
All external services (Firestore, Gemini, SMTP) are mocked — no live connections.
"""
import os
import sys
import pytest
from unittest.mock import MagicMock

# Must be set before any src.main import — these control startup behavior
os.environ['FLASK_ENV'] = 'testing'
os.environ['USE_FIRESTORE'] = 'false'
os.environ['WTF_CSRF_ENABLED'] = 'false'
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-pytest')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.main import app as flask_app, limiter  # noqa: E402

# Disable rate limiting globally for all tests (module-level, runs on import)
limiter.enabled = False
flask_app.config.update({
    'TESTING': True,
    'WTF_CSRF_ENABLED': False,
    'WTF_CSRF_CHECK_DEFAULT': False,
    'SECRET_KEY': 'test-secret-key',
    'RATELIMIT_ENABLED': False,
})

TEST_USER_ID = 'user_test_abc123'
TEST_EMAIL = 'test@example.com'
TEST_ESTATE_ID = 'estate_test_xyz789'


@pytest.fixture(scope='session')
def app():
    yield flask_app


@pytest.fixture
def client(app):
    """Unauthenticated test client."""
    with app.test_client() as c:
        yield c


@pytest.fixture
def authed_client(app):
    """Authenticated test client with session injection."""
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = TEST_USER_ID
            sess['user_email'] = TEST_EMAIL
            sess['estate_id'] = TEST_ESTATE_ID
            sess['current_estate_id'] = TEST_ESTATE_ID
        yield c


@pytest.fixture
def mock_storage(monkeypatch):
    """Replace storage_service with a MagicMock — no Firestore calls."""
    import src.main as m
    mock = MagicMock()
    mock.query_documents.return_value = []
    mock.list_documents.return_value = []
    mock.get_document.return_value = None
    mock.add_document.return_value = True
    mock.update_document.return_value = True
    mock.delete_document.return_value = True
    monkeypatch.setattr(m, 'storage_service', mock)
    return mock


@pytest.fixture
def sample_item():
    """Factory fixture that returns a callable for building item dicts."""
    def _make(name='Test Lamp', **kwargs):
        base = {
            'id': 'item_test_001',
            'estate_id': TEST_ESTATE_ID,
            'name': name,
            'category': 'Furniture',
            'description': 'A test item',
            'estimatedValue': 100.0,
            'destination': 'keep',
            'destinationDetail': '',
            'photos': [],
            'dateAdded': '2024-01-01T00:00:00',
            'lastModified': '2024-01-01T00:00:00',
        }
        base.update(kwargs)
        return base
    return _make


@pytest.fixture
def sample_user():
    """Factory fixture that returns a callable for building user dicts."""
    def _make(email=TEST_EMAIL, name='Test User', **kwargs):
        base = {
            'id': TEST_USER_ID,
            'email': email,
            'name': name,
            'provider': 'email',
            'password_hash': '$2b$12$testhashplaceholder',
            'created_at': '2024-01-01T00:00:00',
            'last_login': '2024-01-01T00:00:00',
            'mfa_enabled': False,
            'account_type': 'free',
        }
        base.update(kwargs)
        return base
    return _make
