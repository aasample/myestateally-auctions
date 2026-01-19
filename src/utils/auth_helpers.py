"""
Authentication helper functions
"""
import os
import bcrypt
import hashlib
from flask import session
import logging

logger = logging.getLogger(__name__)


def hash_password(password):
    """Hash a password using bcrypt or fallback to SHA-256"""
    try:
        # Try bcrypt first (more secure)
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        return hashed.decode('utf-8')
    except Exception as e:
        logger.warning(f"bcrypt failed, using SHA-256 fallback: {e}")
        # Fallback to SHA-256 (less secure, but works everywhere)
        return hashlib.sha256(password.encode('utf-8')).hexdigest()


def verify_password(password, hashed):
    """Verify a password against a hash"""
    try:
        # Try bcrypt first
        if hashed.startswith('$2'):  # bcrypt hash starts with $2
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        else:
            # Fallback to SHA-256 comparison
            return hashlib.sha256(password.encode('utf-8')).hexdigest() == hashed
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def is_authenticated():
    """Check if user is authenticated"""
    return 'user_id' in session


def get_current_user_id():
    """Get current authenticated user ID"""
    return session.get('user_id')


def is_debug_mode():
    """Check if debug endpoints should be enabled"""
    flask_env = os.environ.get('FLASK_ENV', 'production').lower()
    flask_debug = os.environ.get('FLASK_DEBUG', 'false').lower()
    return flask_env == 'development' or flask_debug in ['true', '1', 'on']
