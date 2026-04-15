"""
Sprint 2 — Inventory CRUD
Covers: GET/POST/PUT/DELETE /api/items — auth guards, permissions, validation
"""
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

USER_ID = 'user_inv_test'
ESTATE_ID = 'estate_inv_test'
ITEM_ID = 'item_inv_001'


def authed():
    """Create an authenticated test client."""
    c = app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = USER_ID
        s['user_email'] = 'inv@x.com'
        s['estate_id'] = ESTATE_ID
        s['current_estate_id'] = ESTATE_ID
    return c


class TestGetItems(unittest.TestCase):
    """Sprint 2: GET /api/items"""

    def setUp(self):
        self.c = authed()
        app.config.update({'TESTING': True, 'WTF_CSRF_ENABLED': False})

    def test_unauthenticated_returns_401(self):
        """As a visitor, I cannot access inventory without logging in."""
        self.assertEqual(app.test_client().get('/api/items').status_code, 401)

    def test_no_estate_returns_empty_list(self):
        """As a user with no estate selected, GET items returns empty array."""
        c = app.test_client()
        with c.session_transaction() as s:
            s['user_id'] = USER_ID
        data = c.get('/api/items').get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['items'], [])

    def test_empty_estate_returns_empty_list(self):
        """As a user, an estate with no items returns an empty array."""
        ss = MagicMock()
        ss.query_documents.return_value = []
        with patch.object(main_module, 'storage_service', ss):
            data = self.c.get('/api/items').get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['items'], [])

    def test_populated_estate_returns_all_items(self):
        """As a user, GET items returns all items for my current estate."""
        items = [
            {'id': 'i1', 'estate_id': ESTATE_ID, 'name': 'Lamp', 'estimatedValue': 50},
            {'id': 'i2', 'estate_id': ESTATE_ID, 'name': 'Table', 'estimatedValue': 200},
        ]
        ss = MagicMock()
        ss.query_documents.return_value = items
        with patch.object(main_module, 'storage_service', ss):
            data = self.c.get('/api/items').get_json()
        self.assertEqual(len(data['items']), 2)

    def test_response_is_json(self):
        """As a user, GET items always returns application/json."""
        ss = MagicMock()
        ss.query_documents.return_value = []
        with patch.object(main_module, 'storage_service', ss):
            resp = self.c.get('/api/items')
        self.assertIn('application/json', resp.content_type)


class TestAddItem(unittest.TestCase):
    """Sprint 2: POST /api/items"""

    def setUp(self):
        self.c = authed()
        app.config.update({'TESTING': True, 'WTF_CSRF_ENABLED': False})

    def test_unauthenticated_returns_401(self):
        """As a visitor, I cannot add items to inventory."""
        self.assertEqual(
            app.test_client().post('/api/items', json={'name': 'Vase'}).status_code, 401)

    def test_missing_name_returns_400(self):
        """As a user, I cannot add an item without a name."""
        with patch.object(main_module, 'check_permission', return_value=True):
            resp = self.c.post('/api/items', json={'category': 'Furniture'})
        self.assertEqual(resp.status_code, 400)

    def test_no_estate_returns_400(self):
        """As a user with no estate, adding an item returns 400."""
        c = app.test_client()
        with c.session_transaction() as s:
            s['user_id'] = USER_ID
        with patch.object(main_module, 'check_permission', return_value=True):
            resp = c.post('/api/items', json={'name': 'Chair'})
        self.assertEqual(resp.status_code, 400)

    def test_no_permission_returns_403(self):
        """As a viewer, I am forbidden from adding items."""
        with patch.object(main_module, 'check_permission', return_value=False):
            resp = self.c.post('/api/items', json={'name': 'Chair'})
        self.assertEqual(resp.status_code, 403)

    def test_negative_value_returns_400(self):
        """As a user, I cannot add an item with a negative estimated value."""
        with patch.object(main_module, 'check_permission', return_value=True):
            resp = self.c.post('/api/items', json={'name': 'Chair', 'estimatedValue': -100})
        self.assertEqual(resp.status_code, 400)

    def test_valid_item_created_successfully(self):
        """As an owner, I can add a valid item and receive item data back."""
        ss = MagicMock()
        ss.add_document.return_value = True
        with patch.object(main_module, 'check_permission', return_value=True), \
             patch.object(main_module, 'storage_service', ss), \
             patch.object(main_module, 'log_activity', return_value=True):
            resp = self.c.post('/api/items', json={
                'name': 'Victorian Chair',
                'category': 'Furniture',
                'estimatedValue': 350,
                'destination': 'keep',
            })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['item']['name'], 'Victorian Chair')
        self.assertIn('id', data['item'])

    def test_item_gets_assigned_estate_id(self):
        """As an owner, a newly added item is automatically assigned to the current estate."""
        ss = MagicMock()
        ss.add_document.return_value = True
        with patch.object(main_module, 'check_permission', return_value=True), \
             patch.object(main_module, 'storage_service', ss), \
             patch.object(main_module, 'log_activity', return_value=True):
            resp = self.c.post('/api/items', json={'name': 'Bookshelf'})
        data = resp.get_json()
        self.assertEqual(data['item'].get('estate_id'), ESTATE_ID)


class TestUpdateItem(unittest.TestCase):
    """Sprint 2: PUT /api/items/<id>"""

    def setUp(self):
        self.c = authed()
        app.config.update({'TESTING': True, 'WTF_CSRF_ENABLED': False})

    def test_unauthenticated_returns_401(self):
        """As a visitor, I cannot update items."""
        self.assertEqual(
            app.test_client().put(f'/api/items/{ITEM_ID}', json={}).status_code, 401)

    def test_item_not_found_returns_404(self):
        """As a user, updating a non-existent item returns 404."""
        ss = MagicMock()
        ss.get_document.return_value = None
        with patch.object(main_module, 'check_permission', return_value=True), \
             patch.object(main_module, 'storage_service', ss):
            self.assertEqual(
                self.c.put('/api/items/nonexistent', json={'name': 'x'}).status_code, 404)

    def test_wrong_estate_returns_404(self):
        """As a user, I cannot update an item from a different estate."""
        ss = MagicMock()
        ss.get_document.return_value = {'id': ITEM_ID, 'estate_id': 'other_estate', 'name': 'Lamp'}
        with patch.object(main_module, 'check_permission', return_value=True), \
             patch.object(main_module, 'storage_service', ss):
            self.assertEqual(
                self.c.put(f'/api/items/{ITEM_ID}', json={'name': 'x'}).status_code, 404)

    def test_valid_update_returns_200(self):
        """As an owner, I can update an item's name and category."""
        existing = {'id': ITEM_ID, 'estate_id': ESTATE_ID, 'name': 'Old Lamp', 'category': 'Other'}
        ss = MagicMock()
        ss.get_document.return_value = existing
        ss.add_document.return_value = True
        with patch.object(main_module, 'check_permission', return_value=True), \
             patch.object(main_module, 'storage_service', ss), \
             patch.object(main_module, 'log_activity', return_value=True):
            resp = self.c.put(f'/api/items/{ITEM_ID}',
                              json={'name': 'New Lamp', 'category': 'Furniture'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()['success'])


class TestDeleteItem(unittest.TestCase):
    """Sprint 2: DELETE /api/items/<id>"""

    def setUp(self):
        self.c = authed()
        app.config.update({'TESTING': True, 'WTF_CSRF_ENABLED': False})

    def test_unauthenticated_returns_401(self):
        """As a visitor, I cannot delete items."""
        self.assertEqual(
            app.test_client().delete(f'/api/items/{ITEM_ID}').status_code, 401)

    def test_no_permission_returns_403(self):
        """As a viewer, I am forbidden from deleting items."""
        with patch.object(main_module, 'check_permission', return_value=False):
            self.assertEqual(self.c.delete(f'/api/items/{ITEM_ID}').status_code, 403)

    def test_item_not_found_returns_404(self):
        """As an owner, deleting a non-existent item returns 404."""
        ss = MagicMock()
        ss.get_document.return_value = None
        with patch.object(main_module, 'check_permission', return_value=True), \
             patch.object(main_module, 'storage_service', ss):
            self.assertEqual(self.c.delete('/api/items/ghost_item').status_code, 404)

    def test_valid_delete_returns_200(self):
        """As an owner, I can delete an item and receive a success confirmation."""
        existing = {'id': ITEM_ID, 'estate_id': ESTATE_ID, 'name': 'Lamp'}
        ss = MagicMock()
        ss.get_document.return_value = existing
        ss.delete_document.return_value = True
        with patch.object(main_module, 'check_permission', return_value=True), \
             patch.object(main_module, 'storage_service', ss), \
             patch.object(main_module, 'log_activity', return_value=True):
            resp = self.c.delete(f'/api/items/{ITEM_ID}')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()['success'])

    def test_delete_confirms_item_removed(self):
        """As an owner, after deletion the item is removed from Firestore."""
        existing = {'id': ITEM_ID, 'estate_id': ESTATE_ID, 'name': 'Lamp'}
        ss = MagicMock()
        ss.get_document.return_value = existing
        ss.delete_document.return_value = True
        with patch.object(main_module, 'check_permission', return_value=True), \
             patch.object(main_module, 'storage_service', ss), \
             patch.object(main_module, 'log_activity', return_value=True):
            self.c.delete(f'/api/items/{ITEM_ID}')
        ss.delete_document.assert_called_once_with('inventory', ITEM_ID)


if __name__ == '__main__':
    unittest.main()
