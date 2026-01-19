"""
Storage service for managing JSON and Firestore persistence
"""
import json
import os
import logging

logger = logging.getLogger(__name__)


class StorageService:
    """Unified storage service supporting both JSON files and Firestore"""

    def __init__(self, use_firestore=False):
        self.use_firestore = use_firestore
        self.db = None

        if use_firestore:
            try:
                from google.cloud import firestore
                self.db = firestore.Client()
                logger.info("Firestore client initialized")
            except Exception as e:
                logger.warning(f"Firestore initialization failed: {e}, falling back to JSON")
                self.use_firestore = False

    def load_json(self, filename):
        """Load data from JSON file"""
        try:
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Failed to load {filename}: {e}")
            return {}

    def save_json(self, filename, data):
        """Save data to JSON file"""
        try:
            # On Google App Engine, we can't write to the file system
            if os.environ.get('GAE_ENV'):
                logger.info(f"GAE mode: skipping JSON save for {filename}")
                return False

            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save {filename}: {e}")
            return False

    def get_collection(self, collection_name):
        """Get a Firestore collection or return None"""
        if self.use_firestore and self.db:
            return self.db.collection(collection_name)
        return None

    def add_document(self, collection_name, doc_id, data):
        """Add or update a document in Firestore"""
        if not self.use_firestore or not self.db:
            return False

        try:
            self.db.collection(collection_name).document(doc_id).set(data)
            return True
        except Exception as e:
            logger.error(f"Failed to add document to {collection_name}: {e}")
            return False

    def get_document(self, collection_name, doc_id):
        """Get a document from Firestore"""
        if not self.use_firestore or not self.db:
            return None

        try:
            doc = self.db.collection(collection_name).document(doc_id).get()
            if doc.exists:
                data = doc.to_dict()
                data['id'] = doc.id
                return data
            return None
        except Exception as e:
            logger.error(f"Failed to get document from {collection_name}: {e}")
            return None

    def list_documents(self, collection_name):
        """List all documents in a Firestore collection"""
        if not self.use_firestore or not self.db:
            return None

        try:
            docs = self.db.collection(collection_name).stream()
            items = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                items.append(data)
            return items
        except Exception as e:
            logger.error(f"Failed to list documents from {collection_name}: {e}")
            return None

    def delete_document(self, collection_name, doc_id):
        """Delete a document from Firestore"""
        if not self.use_firestore or not self.db:
            return False

        try:
            self.db.collection(collection_name).document(doc_id).delete()
            return True
        except Exception as e:
            logger.error(f"Failed to delete document from {collection_name}: {e}")
            return False
