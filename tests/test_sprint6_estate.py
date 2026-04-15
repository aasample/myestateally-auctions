"""
Sprint 6 — Estates, QR Code Flow, Exports, Timeline
Covers: GET/POST /api/estates, QR session flow, CSV/PDF exports, estate timeline
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

USER_ID = 'user_estate_test'
ESTATE_ID = 'estate_est_test'


def authed():
    c = app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = USER_ID
        s['user_email'] = 'est@x.com'
        s['estate_id'] = ESTATE_ID
        s['current_estate_id'] = ESTATE_ID
    return c


class TestEstatesCRUD(unittest.TestCase):
    """Sprint 6: GET/POST /api/estates"""

    def setUp(self):
        self.c = authed()
        app.config.update({'TESTING': True, 'WTF_CSRF_ENABLED': False})

    def test_get_unauthenticated_returns_401(self):
        """As a visitor, I cannot view estates."""
        self.assertEqual(app.test_client().get('/api/estates').status_code, 401)

    def test_get_estates_returns_list(self):
        """As a user, GET estates returns all my estates."""
        fake_user = {'id': USER_ID, 'email': 'est@x.com', 'name': 'Test'}
        estates = [{'id': ESTATE_ID, 'name': 'Mom Estate', 'owner_id': USER_ID}]
        with patch.object(main_module, 'get_current_user', return_value=fake_user), \
             patch.object(main_module, 'get_user_estates', return_value=estates):
            resp = self.c.get('/api/estates')
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['estates']), 1)
        self.assertEqual(data['estates'][0]['name'], 'Mom Estate')

    def test_get_estates_empty_returns_empty_list(self):
        """As a new user with no estates, GET estates returns empty list."""
        fake_user = {'id': USER_ID, 'email': 'est@x.com', 'name': 'Test'}
        with patch.object(main_module, 'get_current_user', return_value=fake_user), \
             patch.object(main_module, 'get_user_estates', return_value=[]):
            data = self.c.get('/api/estates').get_json()
        self.assertEqual(data['estates'], [])

    def test_create_estate_missing_name_returns_400(self):
        """As a user, creating an estate without a name returns 400."""
        fake_user = {'id': USER_ID, 'email': 'est@x.com', 'name': 'Test'}
        with patch.object(main_module, 'get_current_user', return_value=fake_user):
            resp = self.c.post('/api/estates', json={})
        self.assertEqual(resp.status_code, 400)

    def test_create_estate_success(self):
        """As a user, I can create a new estate with a name."""
        fake_user = {'id': USER_ID, 'email': 'est@x.com', 'name': 'Test'}
        ss = MagicMock()
        ss.add_document.return_value = True
        with patch.object(main_module, 'get_current_user', return_value=fake_user), \
             patch.object(main_module, 'storage_service', ss), \
             patch.object(main_module, 'firestore_get_user', return_value=fake_user), \
             patch.object(main_module, 'firestore_update_user', return_value=True), \
             patch.object(main_module, 'log_activity', return_value=True):
            resp = self.c.post('/api/estates', json={'name': 'Dad Estate', 'description': 'Test'})
        self.assertIn(resp.status_code, [200, 201])
        self.assertTrue(resp.get_json()['success'])


class TestQRCodeFlow(unittest.TestCase):
    """Sprint 6: QR code generation and photo session flow"""

    def setUp(self):
        self.c = authed()
        app.config.update({'TESTING': True, 'WTF_CSRF_ENABLED': False})

    def test_generate_qr_unauthenticated_returns_401(self):
        """As a visitor, I cannot generate a QR code."""
        self.assertEqual(app.test_client().post('/api/qr/generate').status_code, 401)

    def test_generate_qr_returns_png_base64(self):
        """As a user, generating a QR code returns a base64-encoded PNG image."""
        ss = MagicMock()
        ss.add_document.return_value = True
        with patch.object(main_module, 'storage_service', ss):
            resp = self.c.post('/api/qr/generate')
        data = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(data['success'])
        self.assertTrue(data['qr_code'].startswith('data:image/png;base64,'))
        self.assertIn('session_id', data)
        self.assertIn('upload_url', data)

    def test_generate_photo_session_qr_unauthenticated_returns_401(self):
        """As a visitor, I cannot generate a photo session QR."""
        self.assertEqual(app.test_client().post('/api/qr/photo-session').status_code, 401)

    def test_generate_photo_session_returns_session_id(self):
        """As a user, generating a photo-session QR returns a session_id to poll."""
        ss = MagicMock()
        ss.add_document.return_value = True
        with patch.object(main_module, 'storage_service', ss):
            resp = self.c.post('/api/qr/photo-session')
        data = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(data['success'])
        self.assertIn('session_id', data)
        self.assertTrue(data['qr_code'].startswith('data:image/png;base64,'))

    def test_photo_submit_nonexistent_session_returns_400(self):
        """As mobile, submitting to a non-existent session returns 400."""
        ss = MagicMock()
        ss.get_document.return_value = None
        with patch.object(main_module, 'storage_service', ss):
            resp = app.test_client().post('/api/qr/photo-submit/nonexistent_session_id')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Invalid', resp.get_json()['error'])

    def test_photo_submit_wrong_mode_returns_400(self):
        """As mobile, submitting to a non-photo-only session returns 400."""
        ss = MagicMock()
        ss.get_document.return_value = {'mode': 'full_upload', 'estate_id': ESTATE_ID}
        with patch.object(main_module, 'storage_service', ss):
            resp = app.test_client().post('/api/qr/photo-submit/some_session')
        self.assertEqual(resp.status_code, 400)

    def test_photo_poll_unauthenticated_returns_401(self):
        """As a visitor, I cannot poll for photos."""
        self.assertEqual(
            app.test_client().get('/api/qr/photo-poll/sess123').status_code, 401)

    def test_photo_poll_nonexistent_session_returns_not_ready(self):
        """As a user, polling a non-existent session returns ready=False."""
        ss = MagicMock()
        ss.get_document.return_value = None
        with patch.object(main_module, 'storage_service', ss):
            data = self.c.get('/api/qr/photo-poll/nonexistent').get_json()
        self.assertFalse(data['ready'])

    def test_photo_poll_no_photo_yet_returns_not_ready(self):
        """As a user, polling a session with no photo yet returns ready=False."""
        ss = MagicMock()
        ss.get_document.return_value = {'mode': 'photo_only', 'photo': None}
        with patch.object(main_module, 'storage_service', ss):
            data = self.c.get('/api/qr/photo-poll/sess123').get_json()
        self.assertFalse(data['ready'])

    def test_photo_poll_with_photo_returns_ready_and_consumes(self):
        """As a user, polling a session that has a photo returns ready=True and clears it."""
        photo_data = 'data:image/jpeg;base64,/9j/4AAQSkZJRg=='
        ss = MagicMock()
        ss.get_document.return_value = {'mode': 'photo_only', 'photo': photo_data}
        ss.update_document.return_value = True
        with patch.object(main_module, 'storage_service', ss):
            data = self.c.get('/api/qr/photo-poll/sess123').get_json()
        self.assertTrue(data['ready'])
        self.assertEqual(data['photo'], photo_data)
        # Confirm photo was cleared (consumed once)
        ss.update_document.assert_called_once_with('qr_sessions', 'sess123', {'photo': None})


class TestInventoryExports(unittest.TestCase):
    """Sprint 6: CSV and PDF inventory exports"""

    def setUp(self):
        self.c = authed()
        app.config.update({'TESTING': True, 'WTF_CSRF_ENABLED': False})

    def test_csv_export_unauthenticated_returns_401(self):
        """As a visitor, I cannot export inventory."""
        self.assertEqual(
            app.test_client().get('/api/export/inventory/csv').status_code, 401)

    def test_csv_export_empty_estate_returns_400(self):
        """As a user, exporting an empty estate returns 400 (no items to export)."""
        ss = MagicMock()
        ss.list_documents.return_value = []
        with patch.object(main_module, 'storage_service', ss):
            resp = self.c.get('/api/export/inventory/csv')
        self.assertEqual(resp.status_code, 400)

    def test_csv_export_with_items_includes_data(self):
        """As a user, exporting with items includes each item's name and value."""
        items = [{'id': 'i1', 'estate_id': ESTATE_ID, 'name': 'Antique Vase',
                  'category': 'Collectibles', 'estimatedValue': 500}]
        ss = MagicMock()
        ss.list_documents.return_value = items
        with patch.object(main_module, 'storage_service', ss):
            resp = self.c.get('/api/export/inventory/csv')
        self.assertEqual(resp.status_code, 200)
        content = resp.data.decode('utf-8')
        self.assertIn('Antique Vase', content)

    def test_pdf_export_unauthenticated_returns_401(self):
        """As a visitor, I cannot export inventory as PDF."""
        self.assertEqual(
            app.test_client().get('/api/export/inventory/pdf').status_code, 401)

    def test_pdf_export_with_items_returns_pdf(self):
        """As a user, exporting with items returns a valid PDF file."""
        items = [{'id': 'i1', 'estate_id': ESTATE_ID, 'name': 'Antique Vase',
                  'category': 'Collectibles', 'estimatedValue': 500}]
        ss = MagicMock()
        ss.list_documents.return_value = items
        with patch.object(main_module, 'storage_service', ss):
            resp = self.c.get('/api/export/inventory/pdf')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('pdf', resp.content_type.lower())


class TestEstateTimeline(unittest.TestCase):
    """Sprint 6: GET/POST /api/estate/timeline"""

    def setUp(self):
        self.c = authed()
        app.config.update({'TESTING': True, 'WTF_CSRF_ENABLED': False})

    def test_get_unauthenticated_returns_401(self):
        """As a visitor, I cannot view the estate timeline."""
        self.assertEqual(app.test_client().get('/api/estate/timeline').status_code, 401)

    def test_get_timeline_returns_task_list(self):
        """As a user, GET timeline returns the estate's task list."""
        family = {
            'estate_id': ESTATE_ID,
            'estate_timeline': [
                {'id': 't1', 'task': 'Contact attorney', 'status': 'pending', 'priority': 'high'},
            ]
        }
        with patch.object(main_module, 'get_family_estate_data', return_value=family):
            resp = self.c.get('/api/estate/timeline')
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertIn('timeline', data)

    def test_get_timeline_empty_returns_empty_list(self):
        """As a user with no tasks, GET timeline returns empty list."""
        family = {'estate_id': ESTATE_ID, 'estate_timeline': []}
        with patch.object(main_module, 'get_family_estate_data', return_value=family):
            data = self.c.get('/api/estate/timeline').get_json()
        self.assertEqual(data['timeline'], [])

    def test_add_task_missing_title_returns_400(self):
        """As a user, adding a timeline task without a task description returns 400."""
        family = {'estate_id': ESTATE_ID, 'estate_timeline': []}
        with patch.object(main_module, 'get_family_estate_data', return_value=family):
            resp = self.c.post('/api/estate/timeline', json={})
        self.assertEqual(resp.status_code, 400)

    def test_add_task_success(self):
        """As a user, I can add a task to the estate timeline."""
        family = {'estate_id': ESTATE_ID, 'estate_timeline': []}
        with patch.object(main_module, 'get_family_estate_data', return_value=family), \
             patch.object(main_module, 'firestore_update_family_data', return_value=True):
            resp = self.c.post('/api/estate/timeline',
                               json={'task': 'File probate paperwork', 'priority': 'high'})
        self.assertIn(resp.status_code, [200, 201])


if __name__ == '__main__':
    unittest.main()
