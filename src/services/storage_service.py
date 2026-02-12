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

    def update_document(self, collection_name, doc_id, updates):
        """Update specific fields in a Firestore document"""
        if not self.use_firestore or not self.db:
            return False

        try:
            self.db.collection(collection_name).document(doc_id).update(updates)
            logger.info(f"Updated document {doc_id} in {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to update document in {collection_name}: {e}")
            return False

    def query_documents(self, collection_name, filters=None, order_by=None, limit=None):
        """Query documents in a Firestore collection with filters

        Args:
            collection_name: Name of the collection
            filters: List of tuples (field, operator, value)
                     e.g., [('estate_id', '==', 'abc123')]
            order_by: Field name to order by
            limit: Maximum number of results

        Returns:
            List of documents or None on error
        """
        if not self.use_firestore or not self.db:
            return None

        try:
            query = self.db.collection(collection_name)

            # Apply filters
            if filters:
                for field, operator, value in filters:
                    query = query.where(field, operator, value)

            # Apply ordering
            if order_by:
                query = query.order_by(order_by)

            # Apply limit
            if limit:
                query = query.limit(limit)

            docs = query.stream()
            items = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                items.append(data)

            logger.info(f"Query returned {len(items)} documents from {collection_name}")
            return items
        except Exception as e:
            logger.error(f"Failed to query documents from {collection_name}: {e}")
            return None

    def delete_collection(self, collection_path, batch_size=100):
        """Delete all documents in a collection

        Args:
            collection_path: Path to collection (e.g., 'inventory')
            batch_size: Number of documents to delete per batch
        """
        if not self.use_firestore or not self.db:
            return False

        try:
            coll_ref = self.db.collection(collection_path)
            docs = coll_ref.limit(batch_size).stream()
            deleted = 0

            for doc in docs:
                doc.reference.delete()
                deleted += 1

            if deleted >= batch_size:
                # Recursively delete remaining documents
                return self.delete_collection(collection_path, batch_size)

            logger.info(f"Deleted {deleted} documents from {collection_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection {collection_path}: {e}")
            return False

    def batch_write(self, operations):
        """Execute multiple write operations in a batch

        Args:
            operations: List of dicts with:
                - 'type': 'add'/'update'/'delete'
                - 'collection': collection name
                - 'doc_id': document ID
                - 'data': document data (for add/update)

        Returns:
            True if successful, False otherwise
        """
        if not self.use_firestore or not self.db:
            return False

        try:
            batch = self.db.batch()

            for op in operations:
                doc_ref = self.db.collection(op['collection']).document(op['doc_id'])

                if op['type'] == 'add':
                    batch.set(doc_ref, op['data'])
                elif op['type'] == 'update':
                    batch.update(doc_ref, op['data'])
                elif op['type'] == 'delete':
                    batch.delete(doc_ref)

            batch.commit()
            logger.info(f"Batch write completed: {len(operations)} operations")
            return True
        except Exception as e:
            logger.error(f"Failed to execute batch write: {e}")
            return False
