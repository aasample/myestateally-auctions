"""
Cloud Storage Helper for MyEstateAlly
Handles file uploads to Google Cloud Storage
"""

import os
import logging
from google.cloud import storage
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

# Bucket name
BUCKET_NAME = 'myestateally-uploads'

def get_storage_client():
    """Get Google Cloud Storage client"""
    try:
        return storage.Client()
    except Exception as e:
        logger.error(f"Failed to initialize Storage client: {e}")
        return None

def upload_file_to_gcs(file, filename=None):
    """
    Upload a file to Google Cloud Storage

    Args:
        file: File object or file-like object to upload
        filename: Optional custom filename (will be secured)

    Returns:
        tuple: (success: bool, url_or_error: str)
    """
    try:
        # Secure the filename
        if filename is None:
            filename = secure_filename(file.filename)
        else:
            filename = secure_filename(filename)

        # Get storage client
        client = get_storage_client()
        if not client:
            return False, "Storage client not available"

        # Get bucket
        bucket = client.bucket(BUCKET_NAME)

        # Create blob (file in bucket)
        blob = bucket.blob(f"uploads/{filename}")

        # Upload file
        file.seek(0)  # Reset file pointer to beginning
        blob.upload_from_file(file, content_type=file.content_type if hasattr(file, 'content_type') else 'application/octet-stream')

        # Make the blob publicly readable (optional - adjust based on your needs)
        # blob.make_public()

        # Get the public URL
        url = f"https://storage.googleapis.com/{BUCKET_NAME}/uploads/{filename}"

        logger.info(f"File uploaded successfully: {filename}")
        return True, url

    except Exception as e:
        logger.error(f"Failed to upload file to GCS: {e}")
        return False, str(e)

def upload_bytes_to_gcs(file_bytes, filename, content_type='image/jpeg'):
    """
    Upload bytes directly to Google Cloud Storage

    Args:
        file_bytes: Bytes to upload
        filename: Filename to use
        content_type: MIME type of the file

    Returns:
        tuple: (success: bool, url_or_error: str)
    """
    try:
        # Secure the filename
        filename = secure_filename(filename)

        # Get storage client
        client = get_storage_client()
        if not client:
            return False, "Storage client not available"

        # Get bucket
        bucket = client.bucket(BUCKET_NAME)

        # Create blob
        blob = bucket.blob(f"uploads/{filename}")

        # Upload bytes
        blob.upload_from_string(file_bytes, content_type=content_type)

        # Get the public URL
        url = f"https://storage.googleapis.com/{BUCKET_NAME}/uploads/{filename}"

        logger.info(f"Bytes uploaded successfully: {filename}")
        return True, url

    except Exception as e:
        logger.error(f"Failed to upload bytes to GCS: {e}")
        return False, str(e)

def delete_file_from_gcs(filename):
    """
    Delete a file from Google Cloud Storage

    Args:
        filename: Name of file to delete

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        client = get_storage_client()
        if not client:
            return False

        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"uploads/{filename}")
        blob.delete()

        logger.info(f"File deleted successfully: {filename}")
        return True

    except Exception as e:
        logger.error(f"Failed to delete file from GCS: {e}")
        return False

def get_file_url(filename):
    """
    Get the public URL for a file in Cloud Storage

    Args:
        filename: Name of the file

    Returns:
        str: Public URL of the file
    """
    return f"https://storage.googleapis.com/{BUCKET_NAME}/uploads/{filename}"
