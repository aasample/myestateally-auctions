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
        
        # Get the public URL
        url = f"https://storage.googleapis.com/{BUCKET_NAME}/uploads/{filename}"
        
        logger.info(f"File uploaded successfully: {filename}")
        return True, url
        
    except Exception as e:
        logger.error(f"Failed to upload file to GCS: {e}")
        return False, str(e)

def get_file_url(filename):
    """
    Get the public URL for a file in Cloud Storage
    
    Args:
        filename: Name of the file
    
    Returns:
        str: Public URL of the file
    """
    return f"https://storage.googleapis.com/{BUCKET_NAME}/uploads/{filename}"
