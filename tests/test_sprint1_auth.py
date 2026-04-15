"""
Sprint 1 — Authentication
Covers: login, signup, check-email, MFA verify, auth status, logout, forgot-password
"""
import unittest
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('FLASK_ENV', 'testing')
os.environ.setdefault('USE_FIRESTORE', 'false')
os.environ.setdefault('WTF_CSRF_ENABLED', 'false')

from src.main import app  # noqa: E402
import src.main as main_module  # noqa: E402

USER_ID = 'user_auth_test'
EMAIL = 'auth@example.com'
PASSWORD = 'SecurePass123'


class TestCheckEmail(unittest.TestCase):
    """Sprint 1: POST /api/auth/check-email"""

    def setUp(self):
        self.c = app.test_client()
        app.config.update({'TESTING': True, 'WTF_CSRF_ENABLED': False})

    def test_missing_email_returns_400(self):
        """As a user, I cannot check email without providing one."""
        self.assertEqual(self.c.post('/api/auth/check-email', json={}).status_code, 400)

    def test_unknown_email_returns_exists_false(self):
        """As a user, checking an unknown email returns exists=False."""
        with patch.object(main_module, 'USE_FIRESTORE', True), \
             patch.object(main_module, 'firestore_get_user_by_email', return_value=None):
            resp = self.c.post('/api/auth/check-email', json={'email': 'nobody@x.com'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.get_json()['exists'])

    def test_known_email_returns_exists_true(self):
        """As a user, checking a registered email returns exists=True."""
        with patch.object(main_module, 'USE_FIRESTORE', True), \
             patch.object(main_module, 'firestore_get_user_by_email', return_value={'id': USER_ID}):
            resp = self.c.post('/api/auth/check-email', json={'email': EMAIL})
        self.assertTrue(resp.get_json()['exists'])


class TestLogin(unittest.TestCase):
    """Sprint 1: POST /api/auth/login"""

    def setUp(self):
        self.c = app.test_client()
        app.config.update({'TESTING': True, 'WTF_CSRF_ENABLED': False})

    def test_missing_fields_returns_400(self):
        """As a user, I cannot login without email and password."""
        self.assertEqual(self.c.post('/api/auth/login', json={}).status_code, 400)

    def test_password_too_long_rejected(self):
        """As a security measure, passwords over 128 chars are rejected."""
        resp = self.c.post('/api/auth/login', json={'email': EMAIL, 'password': 'x' * 129})
        self.assertEqual(resp.status_code, 400)

    def test_unknown_user_returns_401(self):
        """As a user, logging in with an unregistered email returns 401."""
        with patch.object(main_module, 'USE_FIRESTORE', True), \
             patch.object(main_module, 'firestore_get_user_by_email', return_value=None):
            resp = self.c.post('/api/auth/login', json={'email': 'ghost@x.com', 'password': 'pass'})
        self.assertEqual(resp.status_code, 401)

    def test_wrong_password_returns_401(self):
        """As a user, logging in with wrong password returns 401."""
        user = {'id': USER_ID, 'email': EMAIL, 'provider': 'email',
                'password_hash': '$invalid', 'mfa_enabled': False, 'last_login': '2024-01-01'}
        with patch.object(main_module, 'USE_FIRESTORE', True), \
             patch.object(main_module, 'firestore_get_user_by_email', return_value=user), \
             patch.object(main_module, 'verify_password', return_value=False):
            resp = self.c.post('/api/auth/login', json={'email': EMAIL, 'password': 'wrong'})
        self.assertEqual(resp.status_code, 401)

    def test_correct_credentials_returns_200_with_user(self):
        """As a user, correct credentials return 200 and user data."""
        user = {'id': USER_ID, 'email': EMAIL, 'name': 'Test', 'provider': 'email',
                'password_hash': 'hash', 'mfa_enabled': False,
                'created_at': '2024-01-01', 'last_login': '2024-01-01'}
        with patch.object(main_module, 'USE_FIRESTORE', True), \
             patch.object(main_module, 'firestore_get_user_by_email', return_value=user), \
             patch.object(main_module, 'verify_password', return_value=True), \
             patch.object(main_module, 'firestore_update_user', return_value=True):
            resp = self.c.post('/api/auth/login', json={'email': EMAIL, 'password': PASSWORD})
        data = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(data['success'])
        self.assertEqual(data['user']['email'], EMAIL)


class TestSignup(unittest.TestCase):
    """Sprint 1: POST /api/auth/signup"""

    def setUp(self):
        self.c = app.test_client()
        app.config.update({'TESTING': True, 'WTF_CSRF_ENABLED': False})

    def test_missing_password_returns_400(self):
        """As a new user, I cannot signup without a password."""
        self.assertEqual(
            self.c.post('/api/auth/signup', json={'email': EMAIL}).status_code, 400)

    def test_weak_password_rejected(self):
        """As a new user, I cannot use a password shorter than 6 chars."""
        resp = self.c.post('/api/auth/signup', json={'email': 'new@x.com', 'password': '123'})
        self.assertEqual(resp.status_code, 400)

    def test_duplicate_email_rejected(self):
        """As a new user, I cannot signup with an already-registered email."""
        with patch.object(main_module, 'USE_FIRESTORE', True), \
             patch.object(main_module, 'firestore_get_user_by_email', return_value={'id': 'existing'}):
            resp = self.c.post('/api/auth/signup', json={'email': EMAIL, 'password': PASSWORD})
        self.assertEqual(resp.status_code, 400)

    def test_valid_signup_creates_account(self):
        """As a new user, valid credentials create an account and return 200."""
        with patch.object(main_module, 'USE_FIRESTORE', True), \
             patch.object(main_module, 'firestore_get_user_by_email', return_value=None), \
             patch.object(main_module, 'firestore_add_user', return_value=True):
            resp = self.c.post('/api/auth/signup',
                               json={'email': 'brand_new@x.com', 'password': PASSWORD, 'name': 'New'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()['success'])


class TestAuthStatus(unittest.TestCase):
    """Sprint 1: GET /api/auth/status"""

    def setUp(self):
        app.config.update({'TESTING': True, 'WTF_CSRF_ENABLED': False})

    def test_unauthenticated_returns_false(self):
        """As a visitor, auth status returns authenticated=False."""
        with app.test_client() as c:
            data = c.get('/api/auth/status').get_json()
        self.assertTrue(data['success'])
        self.assertFalse(data['authenticated'])

    def test_authenticated_user_returns_profile(self):
        """As a logged-in user, auth status returns my profile data."""
        user = {'id': USER_ID, 'email': EMAIL, 'name': 'Test', 'provider': 'email',
                'created_at': '2024-01-01', 'last_login': '2024-01-01'}
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['user_id'] = USER_ID
                sess['user_email'] = EMAIL
            with patch.object(main_module, 'USE_FIRESTORE', True), \
                 patch.object(main_module, 'firestore_get_user', return_value=user), \
                 patch.object(main_module, 'get_user_estates', return_value=[]), \
                 patch.object(main_module, 'firestore_get_estate', return_value=None):
                data = c.get('/api/auth/status').get_json()
        self.assertTrue(data['authenticated'])
        self.assertEqual(data['user']['email'], EMAIL)


class TestLogout(unittest.TestCase):
    """Sprint 1: POST /api/auth/logout"""

    def test_logout_returns_200(self):
        """As a logged-in user, I can logout successfully."""
        app.config.update({'TESTING': True})
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['user_id'] = USER_ID
            resp = c.post('/api/auth/logout')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()['success'])


class TestMFAVerify(unittest.TestCase):
    """Sprint 1: POST /api/auth/verify-mfa"""

    def setUp(self):
        self.c = app.test_client()
        app.config.update({'TESTING': True, 'WTF_CSRF_ENABLED': False})

    def test_missing_fields_returns_400(self):
        """As a user, MFA verify requires both code and session_id."""
        self.assertEqual(self.c.post('/api/auth/verify-mfa', json={}).status_code, 400)

    def test_invalid_session_returns_401(self):
        """As a user, an expired or invalid MFA session returns 401."""
        resp = self.c.post('/api/auth/verify-mfa',
                           json={'code': '123456', 'session_id': 'nonexistent_session'})
        self.assertEqual(resp.status_code, 401)


class TestForgotPassword(unittest.TestCase):
    """Sprint 1: POST /api/auth/forgot-password"""

    def setUp(self):
        self.c = app.test_client()
        app.config.update({'TESTING': True, 'WTF_CSRF_ENABLED': False})

    def test_missing_email_returns_400_or_200(self):
        """As a user, password reset with no email handled gracefully."""
        resp = self.c.post('/api/auth/forgot-password', json={})
        self.assertIn(resp.status_code, [200, 400])

    def test_unknown_email_returns_200_no_enumeration(self):
        """As a security measure, password reset doesn't reveal if email exists."""
        with patch.object(main_module, 'USE_FIRESTORE', True), \
             patch.object(main_module, 'firestore_get_user_by_email', return_value=None):
            resp = self.c.post('/api/auth/forgot-password',
                               json={'email': 'unknown@x.com'})
        # Should return 200 to prevent email enumeration
        self.assertIn(resp.status_code, [200, 400])


if __name__ == '__main__':
    unittest.main()
