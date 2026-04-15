"""
Sprint 5 — Documents
Covers: GET /api/documents, POST /api/documents/upload,
        GET /api/documents/<id>/preview, DELETE /api/documents/<id>
"""
import io
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

USER_ID = 'user_docs_test'
ESTATE_ID = 'estate_docs_test'
DOC_ID = 'doc_test_001'


def authed():
    c = app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = USER_ID
        s['user_email'] = 'docs@x.com'
        s['estate_id'] = ESTATE_ID
        s['current_estate_id'] = ESTATE_ID
    return c


class TestListDocuments(unittest.TestCase):
    """Sprint 5: GET /api/documents"""

    def setUp(self):
        self.c = authed()
        app.config.update({'TESTING': True, 'WTF_CSRF_ENABLED': False})

    def test_unauthenticated_returns_401(self):
        """As a visitor, I cannot view documents."""
        self.assertEqual(app.test_client().get('/api/documents').status_code, 401)

    def test_returns_empty_list_when_no_docs(self):
        """As a user with no documents, GET documents returns an empty list."""
        ss = MagicMock()
        ss.query_documents.return_value = []
        with patch.object(main_module, 'storage_service', ss):
            data = self.c.get('/api/documents').get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['documents'], [])

    def test_returns_documents_for_current_estate(self):
        """As a user, GET documents returns only docs for the current estate."""
        docs = [
            {'id': DOC_ID, 'estate_id': ESTATE_ID, 'name': 'Will.pdf',
             'category': 'Legal', 'access_level': 'all'},
        ]
        ss = MagicMock()
        ss.list_documents.return_value = docs
        with patch.object(main_module, 'storage_service', ss), \
             patch.object(main_module, 'get_user_role_in_estate', return_value='owner'):
            data = self.c.get('/api/documents').get_json()
        self.assertEqual(len(data['documents']), 1)
        self.assertEqual(data['documents'][0]['name'], 'Will.pdf')

    def test_returns_json_content_type(self):
        """As a user, GET documents returns application/json."""
        ss = MagicMock()
        ss.query_documents.return_value = []
        with patch.object(main_module, 'storage_service', ss):
            resp = self.c.get('/api/documents')
        self.assertIn('application/json', resp.content_type)


class TestUploadDocument(unittest.TestCase):
    """Sprint 5: POST /api/documents/upload"""

    def setUp(self):
        self.c = authed()
        app.config.update({'TESTING': True, 'WTF_CSRF_ENABLED': False})

    def test_unauthenticated_returns_401(self):
        """As a visitor, I cannot upload documents."""
        self.assertEqual(app.test_client().post('/api/documents/upload').status_code, 401)

    def test_no_file_field_returns_400(self):
        """As a user, uploading without a file field returns 400."""
        resp = self.c.post('/api/documents/upload',
                           data={}, content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 400)

    def test_empty_filename_returns_400(self):
        """As a user, uploading with no filename returns 400."""
        data = {'file': (io.BytesIO(b'content'), '')}
        resp = self.c.post('/api/documents/upload', data=data,
                           content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 400)

    def test_disallowed_file_type_returns_400(self):
        """As a user, uploading an executable file is rejected."""
        data = {'file': (io.BytesIO(b'content'), 'virus.exe')}
        resp = self.c.post('/api/documents/upload', data=data,
                           content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 400)

    def test_disallowed_batch_file_returns_400(self):
        """As a user, uploading a .bat script is rejected."""
        data = {'file': (io.BytesIO(b'@echo off'), 'script.bat')}
        resp = self.c.post('/api/documents/upload', data=data,
                           content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 400)


class TestPreviewDocument(unittest.TestCase):
    """Sprint 5: GET /api/documents/<id>/preview"""

    def setUp(self):
        self.c = authed()
        app.config.update({'TESTING': True, 'WTF_CSRF_ENABLED': False})

    def test_unauthenticated_returns_401(self):
        """As a visitor, I cannot preview documents."""
        self.assertEqual(
            app.test_client().get(f'/api/documents/{DOC_ID}/preview').status_code, 401)

    def test_nonexistent_doc_returns_404(self):
        """As a user, previewing a document that doesn't exist returns 404."""
        ss = MagicMock()
        ss.get_document.return_value = None
        with patch.object(main_module, 'storage_service', ss):
            resp = self.c.get(f'/api/documents/{DOC_ID}/preview')
        self.assertEqual(resp.status_code, 404)

    def test_wrong_estate_doc_returns_403(self):
        """As a user, I cannot preview a document from a different estate."""
        doc = {'id': DOC_ID, 'estate_id': 'other_estate', 'name': 'Secret.pdf'}
        ss = MagicMock()
        ss.get_document.return_value = doc
        with patch.object(main_module, 'storage_service', ss):
            resp = self.c.get(f'/api/documents/{DOC_ID}/preview')
        self.assertEqual(resp.status_code, 403)


class TestDeleteDocument(unittest.TestCase):
    """Sprint 5: DELETE /api/documents/<id>"""

    def setUp(self):
        self.c = authed()
        app.config.update({'TESTING': True, 'WTF_CSRF_ENABLED': False})

    def test_unauthenticated_returns_401(self):
        """As a visitor, I cannot delete documents."""
        self.assertEqual(
            app.test_client().delete(f'/api/documents/{DOC_ID}').status_code, 401)

    def test_nonexistent_doc_returns_404(self):
        """As a user, deleting a non-existent document returns 404."""
        ss = MagicMock()
        ss.get_document.return_value = None
        with patch.object(main_module, 'storage_service', ss):
            resp = self.c.delete(f'/api/documents/{DOC_ID}')
        self.assertEqual(resp.status_code, 404)

    def test_wrong_estate_returns_403(self):
        """As a user, I cannot delete a document from a different estate."""
        doc = {'id': DOC_ID, 'estate_id': 'other_estate', 'name': 'Other.pdf', 'uploaded_by': USER_ID}
        ss = MagicMock()
        ss.get_document.return_value = doc
        with patch.object(main_module, 'storage_service', ss):
            resp = self.c.delete(f'/api/documents/{DOC_ID}')
        self.assertEqual(resp.status_code, 403)


if __name__ == '__main__':
    unittest.main()
