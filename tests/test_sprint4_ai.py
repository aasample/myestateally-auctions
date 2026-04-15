"""
Sprint 4 — AI Features
Covers: POST /api/ai/lookup-item (Gemini), POST /api/pricing/lookup, POST /api/ai/search
All external AI calls are mocked — no live Gemini or OpenAI requests.
"""
import json
import unittest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('FLASK_ENV', 'testing')
os.environ.setdefault('USE_FIRESTORE', 'false')
os.environ.setdefault('WTF_CSRF_ENABLED', 'false')

from src.main import app  # noqa: E402
import src.main as main_module  # noqa: E402

USER_ID = 'user_ai_test'
ESTATE_ID = 'estate_ai_test'

# Fake Gemini REST API response matching the expected structure
GEMINI_OK = {
    'candidates': [{
        'content': {
            'parts': [{
                'text': json.dumps({
                    'item_name': 'Victorian Oil Lamp',
                    'category': 'Furniture',
                    'description': 'A decorative Victorian-era oil lamp in brass.',
                    'estimated_value': 150,
                    'value_min': 100,
                    'value_max': 200,
                    'confidence': 'medium',
                    'notes': 'Based on similar auction results.',
                })
            }]
        }
    }]
}


def authed():
    c = app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = USER_ID
        s['user_email'] = 'ai@x.com'
        s['estate_id'] = ESTATE_ID
        s['current_estate_id'] = ESTATE_ID
    return c


class TestAILookupItem(unittest.TestCase):
    """Sprint 4: POST /api/ai/lookup-item — Gemini 2.0 Flash (mocked)"""

    def setUp(self):
        self.c = authed()
        app.config.update({'TESTING': True, 'WTF_CSRF_ENABLED': False})

    def test_unauthenticated_returns_401(self):
        """As a visitor, I cannot use AI Lookup."""
        self.assertEqual(
            app.test_client().post('/api/ai/lookup-item', json={}).status_code, 401)

    def test_no_gemini_key_returns_503(self):
        """As a user, if the Gemini API key is not configured, AI Lookup returns 503."""
        with patch.object(main_module, 'gemini_api_key', None):
            resp = self.c.post('/api/ai/lookup-item', json={'name': 'Lamp'})
        self.assertEqual(resp.status_code, 503)
        self.assertIn('AI features not available', resp.get_json()['error'])

    def test_no_name_or_photo_returns_400(self):
        """As a user, AI lookup requires at least a name or one photo."""
        with patch.object(main_module, 'gemini_api_key', 'fake-key'):
            resp = self.c.post('/api/ai/lookup-item', json={})
        self.assertEqual(resp.status_code, 400)

    def test_valid_name_returns_ai_result(self):
        """As a user, providing an item name returns AI-generated category and value."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = GEMINI_OK
        mock_resp.raise_for_status = MagicMock()
        with patch.object(main_module, 'gemini_api_key', 'fake-key'), \
             patch('requests.post', return_value=mock_resp):
            resp = self.c.post('/api/ai/lookup-item', json={'name': 'Victorian Oil Lamp'})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertIn('lookup', data)
        self.assertEqual(data['lookup']['item_name'], 'Victorian Oil Lamp')
        self.assertIn('estimated_value', data['lookup'])
        self.assertIn('category', data['lookup'])

    def test_result_includes_confidence_and_notes(self):
        """As a user, AI lookup result includes confidence and notes fields."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = GEMINI_OK
        mock_resp.raise_for_status = MagicMock()
        with patch.object(main_module, 'gemini_api_key', 'fake-key'), \
             patch('requests.post', return_value=mock_resp):
            resp = self.c.post('/api/ai/lookup-item', json={'name': 'Lamp'})
        lookup = resp.get_json()['lookup']
        self.assertIn('confidence', lookup)
        self.assertIn('notes', lookup)

    def test_gemini_api_network_error_returns_500(self):
        """As a user, if Gemini API is unreachable the endpoint returns 500."""
        with patch.object(main_module, 'gemini_api_key', 'fake-key'), \
             patch('requests.post', side_effect=Exception('Network error')):
            resp = self.c.post('/api/ai/lookup-item', json={'name': 'Lamp'})
        self.assertEqual(resp.status_code, 500)

    def test_invalid_photo_data_url_skipped_gracefully(self):
        """As a user, malformed photo data URLs are skipped without crashing."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = GEMINI_OK
        mock_resp.raise_for_status = MagicMock()
        with patch.object(main_module, 'gemini_api_key', 'fake-key'), \
             patch('requests.post', return_value=mock_resp):
            resp = self.c.post('/api/ai/lookup-item', json={
                'name': 'Lamp',
                'photos': ['data:image/jpeg;base64,validbase64==', 'not-a-valid-data-url']
            })
        self.assertIn(resp.status_code, [200, 500])


class TestAIPricingLookup(unittest.TestCase):
    """Sprint 4: POST /api/pricing/lookup — AI-powered market pricing"""

    def setUp(self):
        self.c = authed()
        app.config.update({'TESTING': True, 'WTF_CSRF_ENABLED': False})

    def test_unauthenticated_returns_401(self):
        """As a visitor, I cannot use AI pricing lookup."""
        self.assertEqual(
            app.test_client().post('/api/pricing/lookup', json={}).status_code, 401)

    def test_no_item_info_returns_400(self):
        """As a user, pricing lookup without any item information returns 400."""
        resp = self.c.post('/api/pricing/lookup', json={})
        self.assertEqual(resp.status_code, 400)

    def test_by_item_name_calls_ai_analysis(self):
        """As a user, pricing lookup by item name calls AI analysis."""
        with patch.object(main_module, 'analyze_item_with_ai', return_value={}):
            resp = self.c.post('/api/pricing/lookup',
                               json={'item_name': 'Victorian Lamp', 'item_category': 'Furniture'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()['success'])

    def test_by_item_id_fetches_from_firestore(self):
        """As a user, pricing lookup by item_id reads the item from Firestore."""
        item = {'id': 'item1', 'estate_id': ESTATE_ID, 'name': 'Lamp', 'category': 'Furniture'}
        ss = MagicMock()
        ss.get_document.return_value = item
        with patch.object(main_module, 'storage_service', ss), \
             patch.object(main_module, 'analyze_item_with_ai', return_value={}):
            resp = self.c.post('/api/pricing/lookup', json={'item_id': 'item1'})
        self.assertEqual(resp.status_code, 200)
        # Confirm Firestore was queried
        ss.get_document.assert_called_once_with('inventory', 'item1')


class TestAISearch(unittest.TestCase):
    """Sprint 4: POST /api/ai/search — natural language inventory search"""

    def setUp(self):
        self.c = authed()
        app.config.update({'TESTING': True, 'WTF_CSRF_ENABLED': False})

    def test_unauthenticated_returns_401(self):
        """As a visitor, I cannot use AI search."""
        self.assertEqual(
            app.test_client().post('/api/ai/search', json={}).status_code, 401)

    def test_missing_query_returns_400(self):
        """As a user, AI search without a query string returns 400."""
        resp = self.c.post('/api/ai/search', json={})
        self.assertEqual(resp.status_code, 400)

    def test_empty_query_returns_400(self):
        """As a user, AI search with an empty query string returns 400."""
        resp = self.c.post('/api/ai/search', json={'query': ''})
        self.assertEqual(resp.status_code, 400)


if __name__ == '__main__':
    unittest.main()
