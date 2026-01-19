"""
Integration tests for API endpoints
"""
import unittest
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Set test environment
os.environ['FLASK_ENV'] = 'testing'
os.environ['FLASK_DEBUG'] = 'false'


class TestAPIEndpoints(unittest.TestCase):
    """Test API endpoint responses"""

    @classmethod
    def setUpClass(cls):
        """Set up test client"""
        from main import app
        cls.app = app
        cls.client = app.test_client()

    def test_index_route(self):
        """Test index route returns 200"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_api_items_endpoint_exists(self):
        """Test that API endpoints are accessible"""
        # Test /api/items endpoint
        response = self.client.get('/api/items')
        # Should return a valid response (200, 400, or 401), not 500
        self.assertIn(response.status_code, [200, 400, 401])
        # Should return JSON
        self.assertIsNotNone(response.get_json())

    def test_login_validation_missing_fields(self):
        """Test login endpoint rejects missing fields"""
        response = self.client.post('/api/auth/login', json={})
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data.get('success'))
        self.assertIn('error', data)

    def test_login_validation_invalid_email(self):
        """Test login endpoint rejects invalid email"""
        response = self.client.post('/api/auth/login', json={
            'email': 'invalid-email',
            'password': 'test123'
        })
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data.get('success'))
        self.assertIn('email', data.get('error', '').lower())

    def test_signup_validation_password_too_short(self):
        """Test signup endpoint rejects short password"""
        response = self.client.post('/api/auth/signup', json={
            'email': 'test@example.com',
            'password': '123'
        })
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data.get('success'))

    def test_debug_endpoint_disabled_in_testing(self):
        """Test debug endpoints are disabled in testing mode"""
        response = self.client.get('/api/debug/version')
        # Should return 403 in non-development mode
        self.assertEqual(response.status_code, 403)

    def test_static_files_accessible(self):
        """Test static files are accessible"""
        # Try to access a common static path
        response = self.client.get('/static/style.css')
        # Should either return 200 (file exists) or 404 (file not found)
        # but not 500 (server error)
        self.assertIn(response.status_code, [200, 404])


if __name__ == '__main__':
    unittest.main()
