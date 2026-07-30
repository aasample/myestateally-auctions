#!/usr/bin/env python3
"""
MyEstateAlly - AI-Powered Estate Management with Family Sharing
A comprehensive estate inventory management system with AI analysis and family collaboration features.
"""

import os
import json
import uuid
import qrcode
import base64
import secrets
import smtplib
import tempfile
import csv
import io
from datetime import datetime, timedelta
from io import BytesIO
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, make_response, url_for, session
from flask_mail import Mail, Message
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.utils import secure_filename
from authlib.integrations.flask_client import OAuth
from authlib.common.security import generate_token
import bcrypt
import hashlib
from dotenv import load_dotenv
from src.utils.image_utils import compress_image_to_base64, compress_image_to_data_url
from src.utils.validation import validate_password_strength
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
import logging
import time
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Set secret key from environment variable (critical for sessions)
SECRET_KEY = os.environ.get('SECRET_KEY', 'myestateally-dev-key-2024-secure-session-key')
app.config['SECRET_KEY'] = SECRET_KEY
app.secret_key = SECRET_KEY  # Also set the secret_key attribute directly

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Log secret key status (first 10 chars only for security)
logger.info(f"Secret key configured: {SECRET_KEY[:10]}... (length: {len(SECRET_KEY)})")

# Email Configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', '587'))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')  # Updated below after get_secret() is defined
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')  # Updated below after get_secret() is defined
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'MyEstateAlly <myestateally33@gmail.com>')

# Initialize Rate Limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)
logger.info("Rate limiting initialized")

# Initialize CSRF Protection
csrf = CSRFProtect(app)
logger.info("CSRF protection initialized")

# Configure CSRF to work with JSON APIs
app.config['WTF_CSRF_CHECK_DEFAULT'] = False  # Don't check by default
app.config['WTF_CSRF_TIME_LIMIT'] = None      # Tokens don't expire
app.config['WTF_CSRF_METHODS'] = ['POST', 'PUT', 'DELETE', 'PATCH']

# Exempt OAuth callbacks from CSRF (they use state parameter instead)
csrf.exempt('auth_google_callback')
csrf.exempt('submit_photo_for_session')   # public mobile endpoint, no CSRF token

# Session cookie configuration for OAuth compatibility
# SameSite=Lax allows cross-site GET redirects (required for OAuth callbacks)
# Secure=True ensures the cookie is only sent over HTTPS
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=10)  # Short-lived for OAuth handshake

# Load environment variables
load_dotenv()

# Helper function to get secrets from Secret Manager
def get_secret(secret_name):
    """Get secret from Google Cloud Secret Manager"""
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'estateally-ai-services')
        secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": secret_path})
        # Strip whitespace to prevent issues with trailing newlines
        return response.payload.data.decode('UTF-8').strip()
    except Exception as e:
        logger.error(f"Failed to get secret {secret_name}: {e}")
        return None

# Update email credentials from Secret Manager (now that get_secret is defined)
if not app.config.get('MAIL_USERNAME'):
    app.config['MAIL_USERNAME'] = get_secret('MAIL_USERNAME') or ''
if not app.config.get('MAIL_PASSWORD'):
    app.config['MAIL_PASSWORD'] = get_secret('MAIL_PASSWORD') or ''

# Initialize Flask-Mail (after credentials are loaded from Secret Manager)
mail = Mail(app)

# Session Configuration - Use Flask's built-in sessions (simpler and more reliable)
# Flask's built-in sessions use signed cookies which work well with the secret key
# Determine if we're in production (HTTPS required) - matches pattern from OAuth callback (line 7110)
is_production_env = os.environ.get('GAE_ENV') is not None
app.config['SESSION_COOKIE_SECURE'] = is_production_env  # Dynamic: True in production (HTTPS), False in dev (HTTP)
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access
# For OAuth to work, we need SameSite=None in production (allows cross-site with Google)
# In dev (HTTP), browsers reject SameSite=None without Secure, so use Lax
app.config['SESSION_COOKIE_SAMESITE'] = 'None' if is_production_env else 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=14)  # Reduced from 30 to 14 days for security

# Note: We're NOT using Flask-Session extension, just Flask's built-in session
# This avoids the secret key configuration issues we were having
logger.info(f"Session: secure={is_production_env}, samesite={'None' if is_production_env else 'Lax'}, GAE_ENV={os.environ.get('GAE_ENV')}")

# OAuth Configuration
oauth = OAuth(app)

# Google OAuth (only if credentials are configured)
google = None
try:
    # Try environment variable first, then Secret Manager
    google_client_id = os.environ.get('GOOGLE_CLIENT_ID') or get_secret('GOOGLE_CLIENT_ID') or ''
    google_client_secret = os.environ.get('GOOGLE_CLIENT_SECRET') or get_secret('GOOGLE_CLIENT_SECRET') or ''

    logger.info(f"Google OAuth credentials loaded: client_id={'present' if google_client_id else 'missing'}, secret={'present' if google_client_secret else 'missing'}")
    logger.info(f"Client ID length: {len(google_client_id)}, starts with: {google_client_id[:15] if google_client_id else 'N/A'}, ends with: {google_client_id[-15:] if google_client_id else 'N/A'}")
    logger.info(f"Client Secret length: {len(google_client_secret)}, starts with: {google_client_secret[:10] if google_client_secret else 'N/A'}, ends with: {google_client_secret[-5:] if google_client_secret else 'N/A'}")

    if google_client_id and google_client_secret:
        google = oauth.register(
            name='google',
            client_id=google_client_id,
            client_secret=google_client_secret,
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={
                'scope': 'openid email profile'
            }
        )
        logger.info("Google OAuth configured successfully")
    else:
        logger.warning("Google OAuth not configured - credentials missing")
except Exception as e:
    logger.warning(f"Failed to configure Google OAuth: {e}")

# Facebook OAuth (only if credentials are configured)
facebook = None
try:
    facebook_client_id = os.environ.get('FACEBOOK_CLIENT_ID', '')
    facebook_client_secret = os.environ.get('FACEBOOK_CLIENT_SECRET', '')

    if facebook_client_id and facebook_client_secret:
        facebook = oauth.register(
            name='facebook',
            client_id=facebook_client_id,
            client_secret=facebook_client_secret,
            server_metadata_url='https://www.facebook.com/.well-known/openid_configuration',
            client_kwargs={'scope': 'email'}
        )
        logger.info("Facebook OAuth configured")
    else:
        logger.warning("Facebook OAuth not configured - credentials missing")
except Exception as e:
    logger.warning(f"Failed to configure Facebook OAuth: {e}")

# File-based storage (replace with database in production)
import json
import os

def load_storage(filename):
    """DEPRECATED: All storage now uses Firestore exclusively
    Kept for backward compatibility - returns empty dict"""
    logger.warning(f"load_storage({filename}) called - deprecated, returning empty dict")
    return {}

def save_storage(filename, data):
    """DEPRECATED: All storage now uses Firestore exclusively
    Kept for backward compatibility - no action taken"""
    logger.warning(f"save_storage({filename}) called - deprecated, no action taken")
    pass

# OpenAI setup for AI features
openai_client = None
try:
    # Try environment variable first, then Secret Manager
    openai_api_key = os.environ.get('OPENAI_API_KEY') or get_secret('OPENAI_API_KEY')
    if openai_api_key:
        openai_client = OpenAI(api_key=openai_api_key)
        logger.info("OpenAI client initialized successfully")
    else:
        logger.warning("OPENAI_API_KEY not found - AI features will be disabled")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}")

# Gemini API key (used for AI Lookup via REST — no extra SDK needed)
gemini_api_key = None
try:
    gemini_api_key = os.environ.get('GEMINI_API_KEY') or get_secret('GEMINI_API_KEY')
    if gemini_api_key:
        logger.info("Gemini API key loaded successfully")
    else:
        logger.warning("GEMINI_API_KEY not found - Gemini AI features will be disabled")
except Exception as e:
    logger.error(f"Failed to load Gemini API key: {e}")

# Firestore (preferred on App Engine) setup
try:
    from google.cloud import firestore  # type: ignore
    from google.cloud import storage  # type: ignore
    _firestore_available = True
    _storage_available = True
except Exception:
    _firestore_available = False
    _storage_available = False

# Initialize StorageService based on environment
from src.services.storage_service import StorageService

USE_FIRESTORE = os.environ.get('USE_FIRESTORE', 'false').lower() in ['true', '1', 'yes']
storage_service = StorageService(use_firestore=USE_FIRESTORE)

if USE_FIRESTORE:
    logger.info("✅ Firestore storage enabled - data will persist across deployments")
else:
    logger.info("⚠️  JSON file storage enabled - data may be lost on deployment")

firestore_client = None
storage_client = None

def get_firestore_client():
    global firestore_client
    if firestore_client is not None:
        return firestore_client
    if not _firestore_available:
        return None
    try:
        firestore_client = firestore.Client()
        logger.info("Firestore client initialized")
        return firestore_client
    except Exception as e:
        logger.error(f"Failed to init Firestore: {e}")
        return None

def get_storage_client():
    """Get Google Cloud Storage client"""
    global storage_client
    if storage_client is not None:
        return storage_client
    if not _storage_available:
        return None
    try:
        storage_client = storage.Client()
        logger.info("Cloud Storage client initialized")
        return storage_client
    except Exception as e:
        logger.error(f"Failed to init Cloud Storage: {e}")
        return None

def get_storage_bucket():
    """Get the Cloud Storage bucket for documents"""
    client = get_storage_client()
    if not client:
        return None

    project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'estateally-ai-services')
    bucket_name = f"{project_id}-documents"

    try:
        bucket = client.bucket(bucket_name)
        # Check if bucket exists, create if not
        if not bucket.exists():
            logger.info(f"Creating storage bucket: {bucket_name}")
            bucket = client.create_bucket(bucket_name, location='us-east1')
            logger.info(f"Bucket created: {bucket_name}")
        return bucket
    except Exception as e:
        logger.error(f"Failed to get/create bucket: {e}")
        return None

def firestore_add_inventory_item(item):
    """Add inventory item to Firestore"""
    return storage_service.add_document('inventory', item['id'], item)

def firestore_list_inventory_items():
    """List inventory items from Firestore"""
    return storage_service.list_documents('inventory')

def firestore_delete_inventory_item(item_id):
    """Delete inventory item from Firestore"""
    return storage_service.delete_document('inventory', item_id)

def firestore_get_inventory_item(item_id):
    """Get a single inventory item from Firestore"""
    return storage_service.get_document('inventory', item_id)

def log_activity(estate_id, user_email, action, item_id=None, item_name=None, details=None):
    """Log an activity to the activity log"""
    try:
        activity_id = str(uuid.uuid4())
        activity = {
            'id': activity_id,
            'estate_id': estate_id,
            'user_email': user_email,
            'action': action,  # 'added', 'updated', 'deleted', 'claimed', 'unclaimed'
            'item_id': item_id,
            'item_name': item_name,
            'details': details or {},
            'timestamp': datetime.now().isoformat()
        }

        # Store in Firestore
        storage_service.add_document('activity_log', activity_id, activity)
        logger.info(f"Activity logged: {action} by {user_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")
        return False

def get_activity_log(estate_id, limit=50):
    """Get activity log for an estate"""
    try:
        all_activities = storage_service.list_documents('activity_log')
        # Filter by estate_id and sort by timestamp
        estate_activities = [
            a for a in all_activities
            if a.get('estate_id') == estate_id
        ]
        # Sort by timestamp descending
        estate_activities.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return estate_activities[:limit]
    except Exception as e:
        logger.error(f"Failed to get activity log: {e}")
        return []

def firestore_update_inventory_item(item):
    """Update inventory item in Firestore"""
    item_id = item.get('id')
    if not item_id:
        logger.error("Cannot update item without ID")
        return False
    return storage_service.add_document('inventory', item_id, item)

def firestore_add_user(user_data):
    """Add user to Firestore"""
    user_id = user_data.get('id') or user_data.get('user_id')
    if not user_id:
        logger.error("Cannot add user without ID")
        return False
    return storage_service.add_document('users', user_id, user_data)

def firestore_get_user(user_id):
    """Get user from Firestore"""
    return storage_service.get_document('users', user_id)

def firestore_get_user_by_email(email):
    """Get user by email from Firestore"""
    if not USE_FIRESTORE or not storage_service.db:
        return None
    try:
        users_ref = storage_service.db.collection('users')
        query = users_ref.where('email', '==', email.lower()).limit(1)
        docs = list(query.stream())
        if docs:
            data = docs[0].to_dict()
            data['id'] = docs[0].id
            return data
        return None
    except Exception as e:
        logger.error(f"Failed to get user by email: {e}")
        return None

def firestore_update_user(user_id, updates):
    """Update user in Firestore"""
    if not USE_FIRESTORE or not storage_service.db:
        return False
    try:
        storage_service.db.collection('users').document(user_id).update(updates)
        return True
    except Exception as e:
        logger.error(f"Failed to update user: {e}")
        return False

# ============================================================================
# FAMILY STORAGE FIRESTORE WRAPPERS
# ============================================================================

def firestore_get_family_data(estate_id):
    """Get family data for an estate from Firestore"""
    doc_id = f"estate_{estate_id}_family"
    return storage_service.get_document('family_data', doc_id)

def firestore_save_family_data(estate_id, family_data):
    """Save family data for an estate to Firestore"""
    doc_id = f"estate_{estate_id}_family"
    family_data['estate_id'] = estate_id
    family_data['id'] = doc_id
    family_data['last_modified'] = datetime.now().isoformat()
    return storage_service.add_document('family_data', doc_id, family_data)

def firestore_update_family_data(estate_id, updates):
    """Update specific fields in family data"""
    doc_id = f"estate_{estate_id}_family"
    updates['last_modified'] = datetime.now().isoformat()
    return storage_service.update_document('family_data', doc_id, updates)

def firestore_add_share_link(share_id, link_data):
    """Add a share link to Firestore"""
    link_data['created_at'] = datetime.now().isoformat()
    return storage_service.add_document('share_links', share_id, link_data)

def firestore_get_share_link(share_id):
    """Get a share link from Firestore"""
    return storage_service.get_document('share_links', share_id)

def firestore_update_share_link(share_id, updates):
    """Update a share link"""
    return storage_service.update_document('share_links', share_id, updates)

# ============================================================================
# ESTATE STORAGE FIRESTORE WRAPPERS
# ============================================================================

def firestore_get_estate(estate_id):
    """Get an estate from Firestore"""
    return storage_service.get_document('estates', estate_id)

def firestore_list_user_estates(user_id):
    """List all estates where user is owner or member"""
    # Get estates where user is owner
    owned = storage_service.query_documents(
        'estates',
        filters=[('owner_id', '==', user_id)]
    ) or []

    # Get user to find member estates
    user = firestore_get_user(user_id)
    member_estate_ids = user.get('estates', []) if user else []

    # Fetch member estates (not owned)
    member = []
    for estate_id in member_estate_ids:
        estate = firestore_get_estate(estate_id)
        if estate and estate.get('owner_id') != user_id:
            member.append(estate)

    return owned + member

def firestore_update_estate(estate_id, updates):
    """Update an estate"""
    updates['last_modified'] = datetime.now().isoformat()
    return storage_service.update_document('estates', estate_id, updates)

def firestore_delete_estate(estate_id):
    """Delete an estate"""
    return storage_service.delete_document('estates', estate_id)

# Load existing data (fallback to JSON if Firestore not enabled)
# inventory_storage removed - now using Firestore exclusively (Phase 2)
# family_storage removed - now using Firestore exclusively (Phase 3)
user_storage = load_storage('users.json') if not USE_FIRESTORE else {}


def get_family_estate_data(estate_id: str) -> dict:
    """Get (or initialize) family sharing data for estate from Firestore"""
    if not estate_id:
        raise ValueError("Estate ID is required")

    # Try to get from Firestore
    family_data = firestore_get_family_data(estate_id)

    # Initialize if doesn't exist
    if not family_data:
        family_data = {
            'estate_id': estate_id,
            'members': {},
            'wanted_items': {},
            'sharing_settings': {
                'enabled': True,
                'show_for_sale_only': False,
                'allow_wanted_tagging': True,
                'max_members': 25
            },
            'share_links': {},
            'assignment_decisions': [],
            'estate_timeline': []
        }
        firestore_save_family_data(estate_id, family_data)
        logger.info(f"Initialized family data for estate {estate_id}")

    return family_data


def save_family_storage():
    """DEPRECATED: Family data now saved to Firestore directly.
    Kept for backward compatibility during migration."""
    logger.info("save_family_storage() called - using Firestore directly")
    pass

# Estate storage removed - now using Firestore exclusively (Phase 4)

# Email notification storage
notification_storage = {
    'preferences': {},  # user_id: {email_notifications, wanted_alerts, inventory_updates, conflict_alerts}
    'queue': [],  # [{type, recipient, subject, body, created_at, attempts}]
    'sent': [],  # [{type, recipient, subject, sent_at, status}]
    'templates': {}  # template_name: {subject, html_body, text_body}
}

# Authentication storage
try:
    auth_storage = load_storage('auth.json')
    if not auth_storage:
        auth_storage = {
            'users': {},  # user_id: {email, name, provider, created_at, last_login, password_hash}
            'sessions': {},  # session_id: {user_id, created_at, expires_at}
            'password_resets': {}  # token: {user_id, created_at, expires_at}
        }
except Exception as e:
    logger.warning(f"Could not load auth storage: {e}")
    auth_storage = {
        'users': {},  # user_id: {email, name, provider, created_at, last_login, password_hash}
        'sessions': {},  # session_id: {user_id, created_at, expires_at}
        'password_resets': {}  # token: {user_id, created_at, expires_at}
    }

# Authentication helper functions
def hash_password(password):
    """Hash a password using bcrypt or fallback to SHA256"""
    try:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    except Exception as e:
        logger.warning(f"bcrypt failed, using SHA256: {e}")
        # Fallback to SHA256 with salt
        salt = secrets.token_hex(16)
        return f"sha256:{salt}:{hashlib.sha256((password + salt).encode()).hexdigest()}"

def verify_password(password, hashed):
    """Verify a password against its hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception as e:
        logger.warning(f"bcrypt verification failed, trying SHA256: {e}")
        # Fallback to SHA256 verification
        if hashed.startswith('sha256:'):
            parts = hashed.split(':')
            if len(parts) == 3:
                salt = parts[1]
                stored_hash = parts[2]
                password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
                return password_hash == stored_hash
        return False

def generate_user_id():
    """Generate a unique user ID"""
    return f"user_{secrets.token_urlsafe(16)}"

def is_authenticated():
    """Check if user is authenticated"""
    return 'user_id' in session

def get_current_user():
    """Get current authenticated user"""
    if not is_authenticated():
        return None
    user_id = session['user_id']

    # Check Firestore first if enabled
    if USE_FIRESTORE:
        user = firestore_get_user(user_id)
        if user:
            return user

    # Fallback to memory storage
    return auth_storage['users'].get(user_id)

def require_auth(f):
    """Decorator to require authentication"""
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def validate_required_fields(data, required_fields):
    """Validate that required fields are present and non-empty"""
    if not data:
        return False, "No data provided"

    for field in required_fields:
        if field not in data or not data[field]:
            return False, f"Missing required field: {field}"

    return True, None

def validate_email(email):
    """Basic email validation"""
    if not email or '@' not in email or '.' not in email.split('@')[1]:
        return False
    return True

ALLOWED_DESTINATIONS = {'keep', 'sell', 'family', 'charity'}

def sanitize_string(value, max_length=500):
    """Sanitize string input to prevent injection attacks"""
    if not isinstance(value, str):
        return str(value)
    # Strip dangerous characters and limit length
    sanitized = value.strip()[:max_length]
    return sanitized

# Allowed file extensions for uploads (security: whitelist approach)
ALLOWED_UPLOAD_EXTENSIONS = {
    # Images
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'heic', 'heif',
    # Documents
    'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt',
    # Spreadsheets
    'xls', 'xlsx', 'csv', 'ods',
    # Other
    'zip'
}

def allowed_file(filename):
    """Check if file extension is allowed (security validation)"""
    if not filename or '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in ALLOWED_UPLOAD_EXTENSIONS

def save_auth_storage():
    """Save authentication data to file or Firestore"""
    try:
        if USE_FIRESTORE:
            logger.info(f"Auth storage using Firestore: {len(auth_storage.get('users', {}))} users in memory")
            # Note: Users are saved individually via firestore_add_user()
            return
        elif os.environ.get('GAE_ENV'):
            logger.info(f"Auth storage updated (GAE mode): {len(auth_storage.get('users', {}))} users")
        else:
            # Local development - save to file
            with open('auth.json', 'w') as f:
                json.dump(auth_storage, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save auth storage: {e}")

# OAuth Configuration (replace with your actual credentials)
OAUTH_CONFIG = {
    'google': {
        'client_id': os.environ.get('GOOGLE_CLIENT_ID', 'your-google-client-id'),
        'client_secret': os.environ.get('GOOGLE_CLIENT_SECRET', 'your-google-client-secret'),
        'redirect_uri': os.environ.get('GOOGLE_REDIRECT_URI', 'https://myestateally.com/auth/google/callback')
    },
    'facebook': {
        'client_id': os.environ.get('FACEBOOK_CLIENT_ID', 'your-facebook-client-id'),
        'client_secret': os.environ.get('FACEBOOK_CLIENT_SECRET', 'your-facebook-client-secret'),
        'redirect_uri': os.environ.get('FACEBOOK_REDIRECT_URI', 'https://myestateally.com/auth/facebook/callback')
    }
}

# Helper functions for authentication
def generate_session_id():
    """Generate a secure session ID"""
    return secrets.token_urlsafe(32)

def create_user_session(user_id):
    """Create a new user session"""
    session_id = generate_session_id()
    auth_storage['sessions'][session_id] = {
        'user_id': user_id,
        'created_at': datetime.now().isoformat(),
        'expires_at': (datetime.now() + timedelta(days=30)).isoformat()
    }
    return session_id

def get_user_from_session(session_id):
    """Get user from session ID"""
    if session_id not in auth_storage['sessions']:
        return None
    
    session = auth_storage['sessions'][session_id]
    expires_at = datetime.fromisoformat(session['expires_at'])
    
    if datetime.now() > expires_at:
        del auth_storage['sessions'][session_id]
        return None
    
    user_id = session['user_id']
    return auth_storage['users'].get(user_id)

# Helper functions for family sharing
def generate_member_code(estate_data: dict) -> str | None:
    """Generate a unique family member code (FM001-FM025) for a specific estate"""
    existing_codes = set(estate_data['members'].keys())
    for i in range(1, 26):  # FM001 to FM025
        code = f"FM{i:03d}"
        if code not in existing_codes:
            return code
    return None  # All codes used

def generate_share_link(estate_id: str) -> str:
    """Generate a secure sharing link for an estate"""
    estate_data = get_family_estate_data(estate_id)
    share_id = secrets.token_urlsafe(16)
    link_info = {
        'estate_id': estate_id,
        'created_at': datetime.now().isoformat(),
        'expires_at': (datetime.now() + timedelta(days=365)).isoformat(),
        'active': True
    }
    estate_data['share_links'][share_id] = link_info
    # Save share link to Firestore
    firestore_add_share_link(share_id, link_info)
    firestore_update_family_data(estate_id, {'share_links': estate_data['share_links']})
    return share_id

def get_shared_inventory(share_id):
    """Get inventory items for family sharing"""
    share_info = family_storage.get('share_links', {}).get(share_id)
    if not share_info:
        return None

    estate_id = share_info.get('estate_id')
    if not estate_id:
        return None

    estate_data = get_family_estate_data(estate_id)
    share_link = estate_data['share_links'].get(share_id)
    if not share_link or not share_link.get('active'):
        return None

    # Check if link has expired
    expires_at = datetime.fromisoformat(share_link['expires_at'])
    if datetime.now() > expires_at:
        share_link['active'] = False
        # Update share link in Firestore
        firestore_update_share_link(share_id, {'active': False})
        estate_data['share_links'][share_id]['active'] = False
        firestore_update_family_data(estate_id, {'share_links': estate_data['share_links']})
        return None

    # Filter inventory based on sharing settings
    items = []
    for item_id, item in inventory_storage.items():
        if item.get('estate_id') != estate_id:
            continue

        if estate_data['sharing_settings']['show_for_sale_only']:
            if item.get('forSale', False):
                items.append(item)
        else:
            items.append(item)

    return items

def get_share_link_context(share_id: str):
    """Get estate_id, estate_data, and share link metadata for a share ID"""
    share_info = family_storage.get('share_links', {}).get(share_id)
    if not share_info:
        return None, None, None

    estate_id = share_info.get('estate_id')
    if not estate_id:
        return None, None, None

    estate_data = get_family_estate_data(estate_id)
    share_link = estate_data['share_links'].get(share_id)
    return estate_id, estate_data, share_link

# Helper functions for estate management
def get_current_estate_id():
    """Get current estate ID from session"""
    return session.get('estate_id')

def get_user_estates(user_id):
    """Get all estates a user belongs to"""
    try:
        # Query Firestore for all estates
        all_estates = storage_service.list_documents('estates')
        user_estates = []

        for estate in all_estates:
            estate_id = estate.get('id')
            # Check if user is owner
            if estate.get('owner_id') == user_id:
                estate['user_role'] = 'owner'
                user_estates.append(estate)
            # Check if user is a member
            elif user_id in estate.get('members', {}):
                member_data = estate['members'][user_id]
                estate['user_role'] = member_data.get('role', 'member')
                user_estates.append(estate)

        return user_estates
    except Exception as e:
        logger.error(f"Error getting user estates from Firestore: {e}")
        # Fallback to in-memory storage
        if user_id not in estate_storage['user_estates']:
            return []
        estate_ids = estate_storage['user_estates'][user_id]
        estates = []
        for estate_id in estate_ids:
            if estate_id in estate_storage['estates']:
                estate = estate_storage['estates'][estate_id].copy()
                estate['id'] = estate_id
                # Add user's role in this estate
                if estate_id in estate_storage['estates']:
                    members = estate_storage['estates'][estate_id].get('members', {})
                    if user_id in members:
                        estate['user_role'] = members[user_id].get('role', 'member')
                    elif estate_storage['estates'][estate_id].get('owner_id') == user_id:
                        estate['user_role'] = 'owner'
                estates.append(estate)
        return estates

def user_has_estate_access(user_id, estate_id):
    """Check if user has access to an estate"""
    if estate_id not in estate_storage['estates']:
        return False
    estate = estate_storage['estates'][estate_id]
    # Owner always has access
    if estate.get('owner_id') == user_id:
        return True
    # Check if user is a member
    members = estate.get('members', {})
    return user_id in members

def save_estate_storage():
    """DEPRECATED: Estate data now saved to Firestore directly.
    Kept for backward compatibility during migration."""
    logger.info("save_estate_storage() called - using Firestore directly")
    pass

# Static file serving
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

# Authentication enforcement configuration
REQUIRE_AUTH_FOR_ALL = os.environ.get('REQUIRE_AUTH_FOR_ALL', 'false').lower() in ['true', '1', 'on']

# Request hook for authentication enforcement
@app.before_request
def redirect_custom_domain_for_oauth():
    """Redirect custom domain to appspot for OAuth until custom domain is fully configured"""
    # Only redirect myestateally.com to appspot for OAuth endpoints
    if 'myestateally.com' in request.host:
        # Redirect non-www to www
        if request.host == 'myestateally.com':
            return redirect(f'https://www.myestateally.com{request.path}', code=301)

        # OAuth is now configured for custom domain - no redirect needed
        # Commenting out redirect to allow OAuth to work on myestateally.com
        # if request.path.startswith('/auth/google'):
        #     appspot_url = f'https://estateally-ai-services.ue.r.appspot.com{request.path}'
        #     if request.query_string:
        #         appspot_url += f'?{request.query_string.decode()}'
        #     return redirect(appspot_url, code=302)

@app.before_request
def enforce_authentication():
    """Enforce authentication for all routes if enabled"""
    if not REQUIRE_AUTH_FOR_ALL:
        return None

    # Allow public endpoints
    public_endpoints = [
        'static_files',
        'index',
        'login',
        'signup',
        'auth_google_login',
        'auth_google_callback',
        'check_email'
    ]

    if request.endpoint in public_endpoints or request.path.startswith('/static/'):
        return None

    # Check if user is authenticated
    if not is_authenticated():
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        return render_template('auth_required.html'), 401

@app.after_request
def set_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'

    # Content-Security-Policy to prevent XSS attacks
    # Note: unsafe-inline and unsafe-eval needed for current app functionality
    # TODO: Remove unsafe-inline/unsafe-eval and use nonces/hashes for better security
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data:; "
        "connect-src 'self';"
    )

    # Only add HSTS in production (when using HTTPS)
    if request.is_secure:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# Main routes
@app.route('/')
def index():
    """
    Main route - shows landing page for non-authenticated users,
    dashboard for authenticated users
    """
    authenticated = is_authenticated()
    user_id = session.get('user_id')
    session_keys = list(session.keys())
    logger.info(f"Index route accessed: authenticated={authenticated}, user_id={user_id}, session_keys={session_keys}")

    if authenticated:
        logger.info(f"Rendering dashboard for authenticated user {user_id}")
        return render_template('index.html')
    else:
        logger.info("User not authenticated, showing landing page")
        return render_template('landing.html')

@app.route('/privacy')
def privacy():
    """Privacy Policy page"""
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    """Terms of Service page"""
    return render_template('terms.html')

# Debug endpoint protection - only enable in development
def is_debug_mode():
    """Check if debug endpoints should be enabled"""
    flask_env = os.environ.get('FLASK_ENV', 'production').lower()
    flask_debug = os.environ.get('FLASK_DEBUG', 'false').lower()
    return flask_env == 'development' or flask_debug in ['true', '1', 'on']

@app.route('/api/debug/version')
def debug_version():
    """Debug endpoint to check if latest code is deployed"""
    if not is_debug_mode():
        return jsonify({'error': 'Debug endpoints are disabled in production'}), 403
    return jsonify({
        'version': '2025-10-03-v3',
        'setupPWA_exists': hasattr(MyEstateAllyApp if 'MyEstateAllyApp' in globals() else type('Dummy', (), {}), 'setupPWA'),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/debug/inventory')
def debug_inventory():
    """Debug endpoint to check inventory data structure"""
    if not is_debug_mode():
        return jsonify({'error': 'Debug endpoints are disabled in production'}), 403
    try:
        # Try Firestore first
        try:
            items = firestore_list_inventory_items()
            if items is not None:
                return jsonify({
                    'success': True,
                    'source': 'firestore',
                    'item_count': len(items),
                    'items': items,
                    'sample_item_structure': items[0] if items else None
                })
        except Exception as firestore_error:
            logger.warning(f"Firestore error in debug: {firestore_error}")
        
        # Try JSON file
        try:
            fresh_storage = load_storage('inventory.json')
            items = list(fresh_storage.values())
            return jsonify({
                'success': True,
                'source': 'json_file',
                'item_count': len(items),
                'items': items,
                'sample_item_structure': items[0] if items else None,
                'json_file_exists': True
            })
        except Exception as json_error:
            logger.warning(f"JSON storage error in debug: {json_error}")
        
        # Fallback to in-memory
        items = list(inventory_storage.values())
        return jsonify({
            'success': True,
            'source': 'in_memory',
            'item_count': len(items),
            'items': items,
            'sample_item_structure': items[0] if items else None,
            'json_file_exists': False
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'inventory_storage_count': len(inventory_storage),
            'inventory_storage_sample': list(inventory_storage.values())[0] if inventory_storage else None
        })

@app.route('/api/debug/test-upload')
def debug_test_upload():
    """Debug endpoint to test item creation"""
    if not is_debug_mode():
        return jsonify({'error': 'Debug endpoints are disabled in production'}), 403
    try:
        # Create a test item
        item_id = str(uuid.uuid4())
        test_item = {
            'id': item_id,
            'name': 'Test Upload Item',
            'category': 'General',
            'description': 'Test item created via debug endpoint.',
            'estimatedValue': 25.0,
            'forSale': False,
            'assignedTo': '',
            'photo': '/static/placeholder-image.png',
            'dateAdded': datetime.now().isoformat(),
            'lastModified': datetime.now().isoformat(),
            'uploadSource': 'debug',
            'sessionId': 'debug-test'
        }
        
        # Save to storage
        inventory_storage[item_id] = test_item
        save_storage('inventory.json', inventory_storage)
        
        return jsonify({
            'success': True,
            'message': f'Created test item {item_id}',
            'item_count': len(inventory_storage),
            'item': test_item
        })
        
    except Exception as e:
        logger.error(f"Error in test upload: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/debug/fix-images')
def debug_fix_images():
    """Debug endpoint to fix image URLs in existing items"""
    if not is_debug_mode():
        return jsonify({'error': 'Debug endpoints are disabled in production'}), 403
    try:
        updated_count = 0
        
        # Update JSON storage first (this is the persistent storage)
        try:
            fresh_storage = load_storage('inventory.json')
            for item_id, item in fresh_storage.items():
                if item.get('photo', '').startswith('/uploads/'):
                    item['photo'] = '/static/placeholder-image.png'
                    item['lastModified'] = datetime.now().isoformat()
                    updated_count += 1
                    logger.info(f"Updated item {item_id} photo URL to placeholder")
            
            if updated_count > 0:
                save_storage('inventory.json', fresh_storage)
                logger.info(f"Saved updated storage with {updated_count} items")
        except Exception as e:
            logger.error(f"Could not update JSON storage: {e}")
        
        # Update in-memory storage to match
        for item_id, item in inventory_storage.items():
            if item.get('photo', '').startswith('/uploads/'):
                item['photo'] = '/static/placeholder-image.png'
                item['lastModified'] = datetime.now().isoformat()
        
        return jsonify({
            'success': True,
            'updated_count': updated_count,
            'message': f'Updated {updated_count} items to use placeholder images'
        })
        
    except Exception as e:
        logger.error(f"Error in fix-images: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/family-view')
def family_view():
    return render_template('family-view.html')

# API Routes for main application
@app.route('/api/items', methods=['GET'])
@require_auth
def get_items():
    """Get all inventory items for the current estate"""
    try:
        logger.info("Fetching inventory items...")
        
        # Get current estate ID
        estate_id = get_current_estate_id()
        if not estate_id:
            # If no estate selected, return empty list (user needs to select/create estate)
            return jsonify({
                'success': True,
                'items': [],
                'message': 'No estate selected'
            })
        
        # Use query for better performance (filter at database level)
        items = storage_service.query_documents(
            'inventory',
            filters=[('estate_id', '==', estate_id)]
        )

        if items is None:
            return jsonify({
                'success': False,
                'error': 'Failed to fetch items from database'
            }), 500

        # Fix image URLs for display
        for item in items:
            if item.get('photo', '').startswith('/uploads/'):
                if item.get('photo_data'):
                    item['photo'] = f"data:image/jpeg;base64,{item['photo_data']}"
                else:
                    item['photo'] = '/static/placeholder-image.png'

        logger.info(f"Found {len(items)} items from Firestore for estate {estate_id}")

        return jsonify({
            'success': True,
            'items': items
        })
        
    except Exception as e:
        logger.error(f"Error fetching items: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': f'Failed to fetch items: {str(e)}'}), 500

@app.route('/api/items', methods=['POST'])
@require_auth
@limiter.limit("50 per hour")
def add_item():
    """Add a new inventory item to the current estate"""
    try:
        user_id = session.get('user_id')
        # Get current estate ID
        estate_id = get_current_estate_id()
        if not estate_id:
            return jsonify({
                'success': False,
                'error': 'No estate selected. Please create or select an estate first.'
            }), 400

        # Check permission to edit (executors and owners can add items)
        if not check_permission(user_id, estate_id, 'edit'):
            return jsonify({
                'success': False,
                'error': 'You do not have permission to add items'
            }), 403

        data = request.get_json()

        # Validate required fields
        valid, error = validate_required_fields(data, ['name'])
        if not valid:
            return jsonify({'success': False, 'error': error}), 400

        # Sanitize inputs
        name = sanitize_string(data.get('name', ''), max_length=200)
        category = sanitize_string(data.get('category', ''), max_length=100)
        description = sanitize_string(data.get('description', ''), max_length=2000)
        family_history = sanitize_string(data.get('familyHistory', ''), max_length=5000)
        destination = data.get('destination', 'keep')
        if destination not in ALLOWED_DESTINATIONS:
            destination = 'keep'
        destination_detail = sanitize_string(data.get('destinationDetail', ''), max_length=200)

        # Handle photos array (base64 data URLs, up to 4 from multi-photo upload)
        photos_raw = data.get('photos', [])
        if not isinstance(photos_raw, list):
            photos_raw = []
        photos = [p for p in photos_raw[:4]
                  if isinstance(p, str) and p.startswith('data:image') and len(p) <= 200000]
        primary_photo = photos[0] if photos else data.get('photo', '')

        # Validate numeric value
        try:
            estimated_value = float(data.get('estimatedValue', 0))
            if estimated_value < 0 or estimated_value > 999999999:
                return jsonify({
                    'success': False,
                    'error': 'Invalid estimated value'
                }), 400
        except (ValueError, TypeError):
            estimated_value = 0

        item_id = str(uuid.uuid4())
        item = {
            'id': item_id,
            'estate_id': estate_id,  # Associate with estate
            'name': name,
            'category': category,
            'description': description,
            'familyHistory': family_history,
            'estimatedValue': estimated_value,
            'destination': destination,
            'destinationDetail': destination_detail,
            'photo': primary_photo,
            'photos': photos,
            'dateAdded': datetime.now().isoformat(),
            'lastModified': datetime.now().isoformat()
        }
        
        # Save to Firestore
        if not firestore_add_inventory_item(item):
            logger.error(f"Failed to add item {item_id} to Firestore")
            return jsonify({
                'success': False,
                'error': 'Failed to save item to database'
            }), 500

        # Log activity
        user_email = session.get('user_email', 'Unknown')
        log_activity(
            estate_id=estate_id,
            user_email=user_email,
            action='added',
            item_id=item_id,
            item_name=name,
            details={'category': category, 'value': estimated_value}
        )

        return jsonify({
            'success': True,
            'message': 'Item added successfully',
            'item': item
        })
        
    except Exception as e:
        logger.error(f"Error adding item: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to add item'
        }), 500

@app.route('/api/items/bulk', methods=['POST'])
@require_auth
@limiter.limit("20 per hour")
def bulk_add_items():
    """Add up to 30 inventory items in a single request (bulk photo import)."""
    try:
        user_id   = session.get('user_id')
        estate_id = get_current_estate_id()
        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400
        if not check_permission(user_id, estate_id, 'edit'):
            return jsonify({'success': False, 'error': 'You do not have permission to add items'}), 403

        data       = request.get_json() or {}
        items_data = data.get('items', [])
        if not isinstance(items_data, list) or not items_data:
            return jsonify({'success': False, 'error': 'No items provided'}), 400
        if len(items_data) > 30:
            return jsonify({'success': False, 'error': 'Maximum 30 items per bulk import'}), 400

        saved  = []
        errors = []

        for idx, item_data in enumerate(items_data):
            try:
                name = sanitize_string(item_data.get('name', ''), max_length=200)
                if not name:
                    errors.append(f"Item {idx + 1}: name is required")
                    continue

                category    = sanitize_string(item_data.get('category', ''),    max_length=100)
                description = sanitize_string(item_data.get('description', ''), max_length=2000)
                destination = item_data.get('destination', 'keep')
                if destination not in ALLOWED_DESTINATIONS:
                    destination = 'keep'

                try:
                    estimated_value = float(item_data.get('estimatedValue', 0))
                    if estimated_value < 0 or estimated_value > 999999999:
                        estimated_value = 0.0
                except (ValueError, TypeError):
                    estimated_value = 0.0

                # Accept a single photo string (base64 data URL, ≤ 200 KB)
                raw_photo   = item_data.get('photo', '')
                raw_photos  = item_data.get('photos', [])
                if not isinstance(raw_photos, list):
                    raw_photos = []
                if raw_photo and isinstance(raw_photo, str) and raw_photo not in raw_photos:
                    raw_photos.insert(0, raw_photo)
                photos = [p for p in raw_photos[:4]
                          if isinstance(p, str) and p.startswith('data:image') and len(p) <= 200000]
                primary_photo = photos[0] if photos else ''

                item_id = str(uuid.uuid4())
                item = {
                    'id':              item_id,
                    'estate_id':       estate_id,
                    'name':            name,
                    'category':        category,
                    'description':     description,
                    'familyHistory':   '',
                    'estimatedValue':  estimated_value,
                    'destination':     destination,
                    'destinationDetail': '',
                    'photo':           primary_photo,
                    'photos':          photos,
                    'dateAdded':       datetime.now().isoformat(),
                    'lastModified':    datetime.now().isoformat(),
                }

                if firestore_add_inventory_item(item):
                    saved.append(item)
                else:
                    errors.append(f"Item {idx + 1} ({name}): database save failed")

            except Exception as e:
                errors.append(f"Item {idx + 1}: {str(e)}")

        if saved:
            user_email = session.get('user_email', 'Unknown')
            log_activity(
                estate_id  = estate_id,
                user_email = user_email,
                action     = 'bulk_imported',
                item_name  = f"{len(saved)} items",
                details    = {'count': len(saved), 'source': 'bulk_photo_import'}
            )

        return jsonify({'success': True, 'saved': len(saved), 'errors': errors, 'items': saved})

    except Exception as e:
        logger.error(f"Error in bulk_add_items: {e}")
        return jsonify({'success': False, 'error': 'Bulk import failed'}), 500


@app.route('/api/items/<item_id>', methods=['PUT'])
@require_auth
@limiter.limit("50 per hour")
def update_item(item_id):
    """Update an existing inventory item"""
    try:
        user_id = session.get('user_id')
        estate_id = get_current_estate_id()

        # Check permission to edit
        if not check_permission(user_id, estate_id, 'edit'):
            return jsonify({
                'success': False,
                'error': 'You do not have permission to edit items'
            }), 403

        data = request.get_json()

        # Get existing item from Firestore
        existing_item = firestore_get_inventory_item(item_id)
        if not existing_item:
            return jsonify({'success': False, 'error': 'Item not found'}), 404

        # Verify estate ownership
        if existing_item.get('estate_id') != estate_id:
            return jsonify({'success': False, 'error': 'Item not found'}), 404

        # Update fields
        item = existing_item.copy()
        item['name'] = data.get('name', item['name'])
        item['category'] = data.get('category', item['category'])
        item['description'] = data.get('description', item.get('description', ''))
        item['familyHistory'] = sanitize_string(data.get('familyHistory', item.get('familyHistory', '')), max_length=5000)
        item['estimatedValue'] = float(data.get('estimatedValue', item.get('estimatedValue') or 0) or 0)
        dest = data.get('destination', item.get('destination', 'keep'))
        if dest not in ALLOWED_DESTINATIONS:
            dest = 'keep'
        item['destination'] = dest
        item['destinationDetail'] = sanitize_string(
            data.get('destinationDetail', item.get('destinationDetail', '')), max_length=200
        )

        # Marketplace listing tracker (Facebook Marketplace / eBay / Craigslist / Poshmark)
        if 'listings' in data and isinstance(data['listings'], dict):
            allowed_platforms = {'facebook', 'ebay', 'craigslist', 'poshmark'}
            item['listings'] = {
                k: bool(v) for k, v in data['listings'].items() if k in allowed_platforms
            }

        item['lastModified'] = datetime.now().isoformat()

        # Handle photo update
        if 'photo_data' in data:
            item['photo_data'] = data['photo_data']
            item['photo'] = f"data:image/jpeg;base64,{data['photo_data']}"
        elif 'photo' in data:
            item['photo'] = data['photo']

        # Save to Firestore
        if not firestore_update_inventory_item(item):
            logger.error(f"Failed to update item {item_id}")
            return jsonify({'success': False, 'error': 'Failed to update item'}), 500

        # Log activity
        user_email = session.get('user_email', 'Unknown')
        log_activity(
            estate_id=estate_id,
            user_email=user_email,
            action='updated',
            item_id=item_id,
            item_name=item.get('name'),
            details={'category': item.get('category'), 'value': item.get('estimatedValue')}
        )

        return jsonify({
            'success': True,
            'message': 'Item updated successfully',
            'item': item
        })
        
    except Exception as e:
        logger.error(f"Error updating item: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to update item'
        }), 500

@app.route('/api/items/<item_id>', methods=['DELETE'])
@require_auth
@limiter.limit("50 per hour")
def delete_item(item_id):
    """Delete an inventory item"""
    try:
        user_id = session.get('user_id')
        estate_id = get_current_estate_id()

        # Check permission to delete - only owner can delete
        if not check_permission(user_id, estate_id, 'delete'):
            return jsonify({
                'success': False,
                'error': 'Only the estate owner can delete items'
            }), 403

        # Get item from Firestore
        item = firestore_get_inventory_item(item_id)
        if not item:
            return jsonify({'success': False, 'error': 'Item not found'}), 404

        # Verify estate ownership
        if item.get('estate_id') != estate_id:
            return jsonify({'success': False, 'error': 'Item not found'}), 404

        item_name = item.get('name', 'Unknown')

        # Delete from Firestore
        if not firestore_delete_inventory_item(item_id):
            logger.error(f"Failed to delete item {item_id}")
            return jsonify({'success': False, 'error': 'Failed to delete item'}), 500

        # Log activity
        user_email = session.get('user_email', 'Unknown')
        log_activity(
            estate_id=estate_id,
            user_email=user_email,
            action='deleted',
            item_id=item_id,
            item_name=item_name
        )

        return jsonify({
            'success': True,
            'message': 'Item deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting item: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to delete item'
        }), 500

def analyze_item_with_ai(item_name, item_description, item_category, item_photo):
    """Use OpenAI Vision API to analyze the item and generate better pricing data"""
    try:
        import openai
        
        # Get OpenAI API key — env var first, then Secret Manager.
        # (Never fall back to SECRET_KEY: that's the Flask session secret,
        # and sending it to OpenAI as a bearer token would leak it.)
        api_key = os.environ.get('OPENAI_API_KEY') or get_secret('OPENAI_API_KEY')

        if not api_key or not api_key.startswith('sk-'):
            logger.warning("OpenAI API key not configured, using basic analysis")
            return None
        
        # Prepare the image for analysis
        image_data = None
        if item_photo:
            if item_photo.startswith('data:image'):
                # Extract base64 data
                image_data = item_photo.split(',')[1] if ',' in item_photo else item_photo
            elif item_photo.startswith('http'):
                image_data = item_photo  # URL format
        
        # Create a detailed prompt for pricing analysis
        prompt = f"""Analyze this item and provide detailed market pricing information:

Item Name: {item_name}
Description: {item_description}
Category: {item_category}

Please provide:
1. Detailed item identification (brand, model, year, condition indicators)
2. Estimated market value range (low, typical, high)
3. Key factors affecting price (condition, rarity, demand, brand value)
4. Recommended selling platforms
5. Best search keywords for finding comparable sales

Format your response as JSON with these fields:
- item_details: detailed description
- brand: identified brand (if any)
- model: model or type
- estimated_age: approximate age or era
- condition_assessment: condition evaluation
- price_low: minimum estimated price
- price_typical: typical market price  
- price_high: maximum estimated price
- price_confidence: confidence score 0-1
- key_factors: array of price-affecting factors
- best_platforms: array of recommended selling platforms
- search_keywords: array of optimal search terms
- market_insights: array of insights"""

        # Call OpenAI API with vision if image available
        client = openai.OpenAI(api_key=api_key)
        
        messages = [{"role": "user", "content": prompt}]
        
        # Add image if available
        if image_data:
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}" if not item_photo.startswith('http') else item_photo}}
                ]
            }]
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # GPT-4o-mini has vision capabilities
            messages=messages,
            max_tokens=1000,
            response_format={"type": "json_object"}
        )
        
        ai_analysis = json.loads(response.choices[0].message.content)
        logger.info(f"AI analysis completed for {item_name}")
        return ai_analysis
        
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        return None

def analyze_uploaded_photo_with_ai(image_data):
    """Use OpenAI Vision API to identify and analyze an uploaded photo"""
    try:
        # Get OpenAI API key — env var first, then Secret Manager
        api_key = os.environ.get('OPENAI_API_KEY') or get_secret('OPENAI_API_KEY')

        if not api_key:
            logger.error("OPENAI_API_KEY not found in environment or Secret Manager")
            return {
                'item_name': 'Uploaded Item',
                'category': 'General',
                'description': 'AI service not configured. Please edit details manually.',
                'estimated_value_min': 0,
                'estimated_value_max': 0,
                'confidence': 0.0
            }

        if not api_key.startswith('sk-'):
            logger.error("OPENAI_API_KEY does not appear to be valid (should start with 'sk-')")
            return {
                'item_name': 'Uploaded Item',
                'category': 'General',
                'description': 'AI service misconfigured. Please edit details manually.',
                'estimated_value_min': 0,
                'estimated_value_max': 0,
                'confidence': 0.0
            }

        # Prepare the image data
        if not image_data:
            logger.warning("No image data provided for AI analysis")
            return {
                'item_name': 'Uploaded Item',
                'category': 'General',
                'description': 'No image data provided.',
                'estimated_value_min': 0,
                'estimated_value_max': 0,
                'confidence': 0.0
            }

        # Handle different image data formats
        image_url = None
        if isinstance(image_data, str):
            if image_data.startswith('data:image'):
                # Data URL format
                image_url = image_data
            elif image_data.startswith('http'):
                # HTTP URL format
                image_url = image_data
            else:
                # Assume it's base64 without the data URL prefix
                image_url = f"data:image/jpeg;base64,{image_data}"

        if not image_url:
            logger.error("Could not format image data for AI analysis")
            return {
                'item_name': 'Uploaded Item',
                'category': 'General',
                'description': 'Image format not supported.',
                'estimated_value_min': 0,
                'estimated_value_max': 0,
                'confidence': 0.0
            }

        # Create a detailed prompt for item identification
        prompt = """You are analyzing a photo to help catalog items in an estate inventory. Be thorough and specific.

Carefully examine this photo and identify the item with as much detail as possible:

1. ITEM NAME: Identify the specific item type. If you can see a brand, model, or distinguishing features, include them. Examples:
   - "Vintage Singer Sewing Machine Model 66"
   - "IKEA Poäng Armchair with Brown Cushion"
   - "Antique Oak Roll-Top Desk"
   - "Apple iPhone 12 Pro (Blue)"

2. CATEGORY: Choose the most specific category from this list:
   Furniture, Electronics, Jewelry, Collectibles, Clothing, Art, Books, Kitchenware, Tools, Sports Equipment, Toys, Musical Instruments, Antiques, Other

3. DESCRIPTION: Write 2-4 sentences describing:
   - Physical condition (excellent, good, fair, worn, damaged)
   - Notable features, markings, or distinguishing characteristics
   - Approximate age or era if visible
   - Material or construction details
   - Any visible brand names, model numbers, or labels

4. ESTIMATED RESALE VALUE: Provide a realistic market value range in USD based on:
   - Item condition
   - Brand reputation and rarity
   - Current market demand
   - Comparable recent sales

5. CONFIDENCE: Rate your identification confidence from 0 to 1:
   - 0.9-1.0: Very confident - clear branding, distinctive features visible
   - 0.7-0.9: Confident - can identify item type and general characteristics
   - 0.5-0.7: Moderate - item type is clear but specifics are uncertain
   - 0.3-0.5: Low - image quality or angle makes identification difficult
   - 0.0-0.3: Very uncertain - need better photo or multiple angles

Be honest about uncertainty. If details are unclear, say so in the description and reflect it in your confidence score.

Format your response as JSON with these exact fields:
{
  "item_name": "string",
  "category": "string",
  "description": "string",
  "estimated_value_min": number,
  "estimated_value_max": number,
  "confidence": number
}"""

        # Call OpenAI API with vision
        client = OpenAI(api_key=api_key)

        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        }]

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=500,
            response_format={"type": "json_object"}
        )

        ai_result = json.loads(response.choices[0].message.content)
        logger.info(f"AI photo analysis completed: {ai_result.get('item_name', 'Unknown')}")

        # Ensure all required fields are present
        result = {
            'item_name': ai_result.get('item_name', 'Uploaded Item'),
            'category': ai_result.get('category', 'General'),
            'description': ai_result.get('description', 'Item uploaded successfully.'),
            'estimated_value_min': ai_result.get('estimated_value_min', 0),
            'estimated_value_max': ai_result.get('estimated_value_max', 0),
            'confidence': ai_result.get('confidence', 0.5)
        }

        return result

    except json.JSONDecodeError as e:
        logger.error(f"AI photo analysis - JSON parsing error: {e}")
        try:
            logger.error(f"Raw response: {response.choices[0].message.content[:500]}")
        except:
            pass
        return {
            'item_name': 'Uploaded Item',
            'category': 'General',
            'description': 'AI response could not be parsed. Please edit details manually.',
            'estimated_value_min': 0,
            'estimated_value_max': 0,
            'confidence': 0.0
        }
    except Exception as e:
        logger.error(f"AI photo analysis error: {e}", exc_info=True)
        logger.error(f"Image data size: {len(str(image_data))} chars")
        return {
            'item_name': 'Uploaded Item',
            'category': 'General',
            'description': f'Item identification failed: {str(e)[:100]}. Please edit details manually.',
            'estimated_value_min': 0,
            'estimated_value_max': 0,
            'confidence': 0.0
        }

@app.route('/api/pricing/lookup', methods=['POST'])
@require_auth
@limiter.limit("30 per hour")
def pricing_lookup():
    """AI-powered pricing lookup across multiple platforms"""
    try:
        data = request.get_json()
        item_id = data.get('item_id')
        item_name = data.get('item_name', '')
        item_description = data.get('item_description', '')
        item_category = data.get('item_category', '')
        item_photo = data.get('item_photo', '')
        
        if not item_id and not item_name:
            return jsonify({
                'success': False,
                'error': 'Item ID or name required'
            }), 400
        
        # Get item details from inventory if item_id provided
        if item_id:
            item = storage_service.get_document('inventory', item_id)
            
            if item:
                item_name = item.get('name', item_name)
                item_description = item.get('description', item_description)
                item_category = item.get('category', item_category)
                item_photo = item.get('photo', item_photo)
                # Get photo_data if available
                if not item_photo and item.get('photo_data'):
                    item_photo = f"data:image/jpeg;base64,{item['photo_data']}"
        
        # Use AI to analyze the item and get better pricing
        ai_analysis = analyze_item_with_ai(item_name, item_description, item_category, item_photo)
        
        # Generate search query - enhanced with AI insights
        if ai_analysis and ai_analysis.get('search_keywords'):
            search_query = ' '.join(ai_analysis['search_keywords'][:3])
        else:
            search_query = f"{item_name} {item_category}".strip()
        
        # Use AI-powered pricing if available, otherwise use intelligent estimates
        if ai_analysis:
            price_low = float(ai_analysis.get('price_low', 20))
            price_typical = float(ai_analysis.get('price_typical', 50))
            price_high = float(ai_analysis.get('price_high', 100))
            confidence = float(ai_analysis.get('price_confidence', 0.75))
            brand_info = f"{ai_analysis.get('brand', '')} " if ai_analysis.get('brand') else ""
            model_info = ai_analysis.get('model', '')
        else:
            # Fallback to smarter estimates based on category
            base_price = {
                'Furniture': 150, 'Jewelry': 100, 'Art': 200, 'Electronics': 75,
                'Collectibles': 50, 'Antiques': 300, 'Clothing': 30, 'Books': 15
            }.get(item_category, 50)
            price_low = round(base_price * 0.5, 2)
            price_typical = round(base_price, 2)
            price_high = round(base_price * 2.5, 2)
            confidence = 0.60
            brand_info = ""
            model_info = ""
        
        # Generate platform-specific pricing with realistic variations
        pricing_results = {
            'item_name': item_name,
            'search_query': search_query,
            'timestamp': datetime.now().isoformat(),
            'ai_enhanced': ai_analysis is not None,
            'platforms': {
                'ebay': {
                    'name': 'eBay',
                    'icon': 'fas fa-shopping-cart',
                    'results': [
                        {
                            'title': f'{brand_info}{item_name} - Good Condition {model_info}'.strip(),
                            'price': round(price_typical * 0.8, 2),
                            'condition': 'Used',
                            'url': f'https://www.ebay.com/sch/i.html?_nkw={search_query.replace(" ", "+")}',
                            'sold_date': '2025-09-15',
                            'confidence': round(confidence, 2)
                        },
                        {
                            'title': f'{brand_info}{item_name} - Excellent Condition'.strip(),
                            'price': round(price_typical * 1.2, 2),
                            'condition': 'Used - Excellent',
                            'url': f'https://www.ebay.com/sch/i.html?_nkw={search_query.replace(" ", "+")}&LH_Sold=1',
                            'sold_date': '2025-09-10',
                            'confidence': round(confidence + 0.1, 2)
                        }
                    ],
                    'average_price': round(price_typical, 2),
                    'price_range': {
                        'min': round(price_low * 0.9, 2),
                        'max': round(price_high * 0.9, 2)
                    }
                },
                'amazon': {
                    'name': 'Amazon',
                    'icon': 'fab fa-amazon',
                    'results': [
                        {
                            'title': f'{brand_info}{item_name} - New'.strip(),
                            'price': round(price_high * 0.85, 2),
                            'condition': 'New',
                            'url': f'https://www.amazon.com/s?k={search_query.replace(" ", "+")}',
                            'sold_date': '2025-09-20',
                            'confidence': round(confidence - 0.05, 2)
                        }
                    ],
                    'average_price': round(price_high * 0.85, 2),
                    'price_range': {
                        'min': round(price_typical, 2),
                        'max': round(price_high * 1.1, 2)
                    }
                },
                'facebook_marketplace': {
                    'name': 'Facebook Marketplace',
                    'icon': 'fab fa-facebook',
                    'results': [
                        {
                            'title': f'{item_name} - Local Pickup',
                            'price': round(price_low * 1.2, 2),
                            'condition': 'Used',
                            'url': f'https://www.facebook.com/marketplace/search/?query={search_query.replace(" ", "%20")}',
                            'sold_date': '2025-09-18',
                            'confidence': round(confidence - 0.15, 2)
                        }
                    ],
                    'average_price': round(price_low * 1.2, 2),
                    'price_range': {
                        'min': round(price_low * 0.7, 2),
                        'max': round(price_typical * 0.8, 2)
                    }
                },
                'etsy': {
                    'name': 'Etsy',
                    'icon': 'fab fa-etsy',
                    'results': [
                        {
                            'title': f'Vintage {item_name}' if item_category in ['Antiques', 'Collectibles', 'Art'] else f'{item_name}',
                            'price': round(price_typical * 1.1, 2),
                            'condition': 'Vintage' if item_category in ['Antiques', 'Collectibles'] else 'Handmade/Unique',
                            'url': f'https://www.etsy.com/search?q={search_query.replace(" ", "+")}',
                            'sold_date': '2025-09-12',
                            'confidence': round(confidence - 0.1, 2)
                        }
                    ],
                    'average_price': round(price_typical * 1.1, 2),
                    'price_range': {
                        'min': round(price_typical * 0.7, 2),
                        'max': round(price_high, 2)
                    }
                }
            },
            'ai_analysis': {
                'market_trend': 'stable',
                'recommended_price': round(price_typical, 2),
                'confidence_score': round(confidence, 2),
                'market_insights': ai_analysis.get('market_insights', []) if ai_analysis else [
                    f'Estimated market value based on {item_category} category',
                    'Condition is a key factor in pricing',
                    'Local marketplace prices tend to be lower than online platforms',
                    'Consider getting item professionally appraised for accurate valuation'
                ],
                'selling_recommendations': ai_analysis.get('key_factors', []) if ai_analysis else [
                    'Take high-quality, well-lit photos from multiple angles',
                    'Research completed sales on eBay for comparable items',
                    'Provide detailed descriptions including brand, condition, and measurements',
                    'Consider professional appraisal for high-value items'
                ],
                'item_details': ai_analysis.get('item_details', f'{item_name} - {item_category}') if ai_analysis else f'{item_name} - {item_category}',
                'condition_assessment': ai_analysis.get('condition_assessment', 'Unable to assess without image') if ai_analysis else 'Unable to assess without image'
            },
            'summary': {
                'overall_average': round(35 + (hash(item_name) % 100), 2),
                'price_range': {
                    'min': round(15 + (hash(item_name) % 40), 2),
                    'max': round(80 + (hash(item_name) % 200), 2)
                },
                'platform_count': 4,
                'total_results': 6
            }
        }
        
        logger.info(f"Pricing lookup completed for: {item_name}")
        
        return jsonify({
            'success': True,
            'data': pricing_results
        })
        
    except Exception as e:
        logger.error(f"Error in pricing lookup: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': 'Failed to lookup pricing'
        }), 500

@app.route('/api/pricing/history/<item_id>')
@require_auth
def pricing_history(item_id):
    """Get pricing history for an item"""
    try:
        # Mock pricing history (in real app, this would come from database)
        history = {
            'item_id': item_id,
            'history': [
                {
                    'date': '2025-09-01',
                    'average_price': 45.50,
                    'platform': 'all',
                    'volume': 12
                },
                {
                    'date': '2025-09-15',
                    'average_price': 48.75,
                    'platform': 'all',
                    'volume': 8
                },
                {
                    'date': '2025-10-01',
                    'average_price': 52.00,
                    'platform': 'all',
                    'volume': 15
                }
            ]
        }
        
        return jsonify({
            'success': True,
            'data': history
        })
        
    except Exception as e:
        logger.error(f"Error getting pricing history: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get pricing history'
        }), 500

# ============================================================================
# DOCUMENT MANAGEMENT ENDPOINTS
# ============================================================================

ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'txt'}
DOCUMENT_CATEGORIES = [
    'Will',
    'Trust',
    'Deed',
    'Title',
    'Insurance Policy',
    'Appraisal',
    'Receipt',
    'Warranty',
    'Certificate',
    'Tax Document',
    'Other'
]

def allowed_document_file(filename):
    """Check if file extension is allowed for documents"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_DOCUMENT_EXTENSIONS

@app.route('/api/documents', methods=['GET'])
@require_auth
def get_documents():
    """Get all documents for the authenticated user's estate"""
    try:
        user_id = session.get('user_id')
        estate_id = session.get('current_estate_id')

        if not estate_id:
            # Return empty list if no estate selected (happens during initial load)
            return jsonify({
                'success': True,
                'documents': []
            })

        # Get documents from Firestore
        documents = storage_service.list_documents('documents')

        # Filter to only this estate's documents
        estate_documents = [
            doc for doc in documents
            if doc.get('estate_id') == estate_id
        ]

        # Filter based on user role and document permissions
        user_email = session.get('user_email')
        user_role = get_user_role_in_estate(user_id, estate_id)

        filtered_documents = []
        for doc in estate_documents:
            access_level = doc.get('access_level', 'all')
            shared_with = doc.get('shared_with', [])

            # Check if user has access
            if access_level == 'all':
                filtered_documents.append(doc)
            elif access_level == 'executor_only' and user_role in ['owner', 'executor']:
                filtered_documents.append(doc)
            elif access_level == 'owner_only' and user_role == 'owner':
                filtered_documents.append(doc)
            elif user_email in shared_with:
                filtered_documents.append(doc)

        return jsonify({
            'success': True,
            'documents': filtered_documents
        })

    except Exception as e:
        logger.error(f"Error getting documents: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get documents'
        }), 500

@app.route('/api/documents/upload', methods=['POST'])
@require_auth
@limiter.limit("20 per hour")
def upload_document():
    """Upload a document to Cloud Storage"""
    try:
        user_id = session.get('user_id')
        estate_id = session.get('current_estate_id')

        if not estate_id:
            return jsonify({
                'success': False,
                'error': 'No estate selected'
            }), 400

        # Check if file is present
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided'
            }), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400

        if not allowed_document_file(file.filename):
            return jsonify({
                'success': False,
                'error': f'File type not allowed. Allowed types: {", ".join(ALLOWED_DOCUMENT_EXTENSIONS)}'
            }), 400

        # Get document metadata from form
        category = request.form.get('category', 'Other')
        description = request.form.get('description', '')

        if category not in DOCUMENT_CATEGORIES:
            category = 'Other'

        # Generate unique document ID
        doc_id = str(uuid.uuid4())

        # Secure the filename
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()

        # Create storage path: estate_id/doc_id.extension
        storage_filename = f"{estate_id}/{doc_id}.{file_extension}"

        # Upload to Cloud Storage
        bucket = get_storage_bucket()
        if not bucket:
            return jsonify({
                'success': False,
                'error': 'Storage service unavailable'
            }), 503

        blob = bucket.blob(storage_filename)
        blob.upload_from_file(file, content_type=file.content_type)

        # Make the file private (require authentication to download)
        blob.metadata = {
            'estate_id': estate_id,
            'user_id': user_id,
            'original_filename': original_filename
        }
        blob.patch()

        # Save document metadata to Firestore
        document_data = {
            'id': doc_id,
            'estate_id': estate_id,
            'user_id': user_id,
            'filename': original_filename,
            'storage_path': storage_filename,
            'category': category,
            'description': description,
            'file_size': blob.size,
            'content_type': file.content_type,
            'uploaded_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }

        storage_service.add_document('documents', doc_id, document_data)

        logger.info(f"Document uploaded: {doc_id} - {original_filename}")

        return jsonify({
            'success': True,
            'message': 'Document uploaded successfully',
            'document': document_data
        })

    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to upload document'
        }), 500

@app.route('/api/documents/<doc_id>', methods=['GET'])
@require_auth
def download_document(doc_id):
    """Download a document from Cloud Storage"""
    try:
        user_id = session.get('user_id')
        estate_id = session.get('current_estate_id')

        if not estate_id:
            return jsonify({
                'success': False,
                'error': 'No estate selected'
            }), 400

        # Get document metadata from Firestore
        doc_data = storage_service.get_document('documents', doc_id)

        if not doc_data:
            return jsonify({
                'success': False,
                'error': 'Document not found'
            }), 404

        # Verify document belongs to user's estate
        if doc_data.get('estate_id') != estate_id:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403

        # Get file from Cloud Storage
        bucket = get_storage_bucket()
        if not bucket:
            return jsonify({
                'success': False,
                'error': 'Storage service unavailable'
            }), 503

        blob = bucket.blob(doc_data['storage_path'])

        if not blob.exists():
            return jsonify({
                'success': False,
                'error': 'Document file not found in storage'
            }), 404

        # Download to bytes
        file_data = blob.download_as_bytes()

        # Create response with file
        response = make_response(file_data)
        response.headers['Content-Type'] = doc_data.get('content_type', 'application/octet-stream')
        response.headers['Content-Disposition'] = f'attachment; filename="{doc_data["filename"]}"'

        return response

    except Exception as e:
        logger.error(f"Error downloading document: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to download document'
        }), 500

@app.route('/api/documents/<doc_id>/preview', methods=['GET'])
@require_auth
@limiter.limit("100 per hour")
def preview_document(doc_id):
    """Preview a document in-browser (PDF or image)"""
    try:
        user_id = session.get('user_id')
        estate_id = session.get('current_estate_id')

        if not estate_id:
            return jsonify({
                'success': False,
                'error': 'No estate selected'
            }), 400

        # Get document metadata from Firestore
        doc_data = storage_service.get_document('documents', doc_id)

        if not doc_data:
            return jsonify({
                'success': False,
                'error': 'Document not found'
            }), 404

        # Verify document belongs to user's estate
        if doc_data.get('estate_id') != estate_id:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403

        # Get file from Cloud Storage
        bucket = get_storage_bucket()
        if not bucket:
            return jsonify({
                'success': False,
                'error': 'Storage service unavailable'
            }), 503

        blob = bucket.blob(doc_data['storage_path'])

        if not blob.exists():
            return jsonify({
                'success': False,
                'error': 'Document file not found in storage'
            }), 404

        # Download to bytes
        file_data = blob.download_as_bytes()

        # Create response with file for in-browser preview
        response = make_response(file_data)
        response.headers['Content-Type'] = doc_data.get('content_type', 'application/octet-stream')
        # Use 'inline' instead of 'attachment' to enable browser preview
        response.headers['Content-Disposition'] = f'inline; filename="{doc_data["filename"]}"'
        # Prevent caching of sensitive documents
        response.headers['Cache-Control'] = 'no-store, private'

        return response

    except Exception as e:
        logger.error(f"Error previewing document: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to preview document'
        }), 500

@app.route('/api/documents/<doc_id>', methods=['DELETE'])
@require_auth
def delete_document(doc_id):
    """Delete a document"""
    try:
        user_id = session.get('user_id')
        estate_id = session.get('current_estate_id')

        if not estate_id:
            return jsonify({
                'success': False,
                'error': 'No estate selected'
            }), 400

        # Get document metadata
        doc_data = storage_service.get_document('documents', doc_id)

        if not doc_data:
            return jsonify({
                'success': False,
                'error': 'Document not found'
            }), 404

        # Verify document belongs to user's estate
        if doc_data.get('estate_id') != estate_id:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403

        # Delete from Cloud Storage
        bucket = get_storage_bucket()
        if bucket:
            blob = bucket.blob(doc_data['storage_path'])
            if blob.exists():
                blob.delete()

        # Delete metadata from Firestore
        storage_service.delete_document('documents', doc_id)

        logger.info(f"Document deleted: {doc_id}")

        return jsonify({
            'success': True,
            'message': 'Document deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to delete document'
        }), 500

@app.route('/api/documents/categories', methods=['GET'])
@require_auth
def get_document_categories():
    """Get list of available document categories"""
    return jsonify({
        'success': True,
        'categories': DOCUMENT_CATEGORIES
    })

@app.route('/api/documents/<doc_id>/permissions', methods=['PUT'])
@require_auth
def update_document_permissions(doc_id):
    """Update document access permissions"""
    try:
        user_id = session.get('user_id')
        estate_id = get_current_estate_id()

        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        # Only owner and executors can manage document permissions
        if not check_permission(user_id, estate_id, 'manage_members'):
            return jsonify({
                'success': False,
                'error': 'You do not have permission to manage document permissions'
            }), 403

        data = request.get_json()
        access_level = data.get('access_level', 'all')  # 'all', 'executor_only', 'owner_only'

        # Get documents from storage
        documents = storage_service.list_documents('documents')
        doc = None
        for d in documents:
            if d.get('id') == doc_id and d.get('estate_id') == estate_id:
                doc = d
                break

        if not doc:
            return jsonify({'success': False, 'error': 'Document not found'}), 404

        # Update access level
        doc['access_level'] = access_level
        doc['lastModified'] = datetime.now().isoformat()

        # Save to Firestore
        storage_service.update_document('documents', doc_id, doc)

        return jsonify({
            'success': True,
            'message': 'Document permissions updated',
            'document': doc
        })

    except Exception as e:
        logger.error(f"Error updating document permissions: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to update permissions'
        }), 500

@app.route('/api/documents/<doc_id>/share', methods=['POST'])
@require_auth
def share_document(doc_id):
    """Share a document with specific family members"""
    try:
        user_id = session.get('user_id')
        estate_id = get_current_estate_id()

        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        # Check permission
        if not check_permission(user_id, estate_id, 'manage_members'):
            return jsonify({
                'success': False,
                'error': 'You do not have permission to share documents'
            }), 403

        data = request.get_json()
        shared_with = data.get('shared_with', [])  # List of email addresses

        # Get document
        documents = storage_service.list_documents('documents')
        doc = None
        for d in documents:
            if d.get('id') == doc_id and d.get('estate_id') == estate_id:
                doc = d
                break

        if not doc:
            return jsonify({'success': False, 'error': 'Document not found'}), 404

        # Update shared_with list
        doc['shared_with'] = shared_with
        doc['lastModified'] = datetime.now().isoformat()

        # Save to Firestore
        storage_service.update_document('documents', doc_id, doc)

        return jsonify({
            'success': True,
            'message': 'Document shared successfully',
            'document': doc
        })

    except Exception as e:
        logger.error(f"Error sharing document: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to share document'
        }), 500

@app.route('/api/debug/test-auth')
def debug_test_auth():
    """Debug endpoint to test authentication components"""
    if not is_debug_mode():
        return jsonify({'error': 'Debug endpoints are disabled in production'}), 403
    try:
        test_password = "test123"
        hashed = hash_password(test_password)
        verified = verify_password(test_password, hashed)
        
        return jsonify({
            'success': True,
            'password_test': {
                'original': test_password,
                'hashed': hashed[:50] + '...' if len(hashed) > 50 else hashed,
                'verified': verified
            },
            'bcrypt_available': True,
            'session_configured': 'SECRET_KEY' in app.config
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'bcrypt_available': False
        }), 500

@app.route('/api/debug/email-status')
def debug_email_status():
    """Debug endpoint to check email configuration and sent emails"""
    if not is_debug_mode():
        return jsonify({'error': 'Debug endpoints are disabled in production'}), 403
    try:
        return jsonify({
            'success': True,
            'email_config': {
                'mail_server': app.config['MAIL_SERVER'],
                'mail_port': app.config['MAIL_PORT'],
                'mail_use_tls': app.config['MAIL_USE_TLS'],
                'mail_username': '***' if app.config['MAIL_USERNAME'] else 'Not configured',
                'mail_password': '***' if app.config['MAIL_PASSWORD'] else 'Not configured',
                'mail_default_sender': app.config['MAIL_DEFAULT_SENDER']
            },
            'sent_emails': notification_storage['sent'][-10:],  # Last 10 emails
            'family_estates': {
                estate_id: list(estate_data.get('members', {}).keys())
                for estate_id, estate_data in family_storage.get('estates', {}).items()
            }
        })
    except Exception as e:
        logger.error(f"Error in email status debug: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/hero/upload', methods=['POST'])
@require_auth
@limiter.limit("20 per hour")
def hero_upload():
    """Handle photo upload and AI analysis"""
    try:
        if 'photo' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No photo provided'
            }), 400
        
        file = request.files['photo']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400

        # Security: Validate file type
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': 'Invalid file type. Allowed types: images (PNG, JPG, GIF, WebP, SVG) and documents (PDF)'
            }), 400

        # Save uploaded file (in production, use cloud storage)
        filename = secure_filename(file.filename)
        upload_dir = os.path.join(tempfile.gettempdir(), 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)

        # Compress image and convert to base64 for AI analysis
        import os as os_module
        original_size_kb = os_module.path.getsize(file_path) / 1024
        logger.info(f"Compressing image for AI analysis: {filename} (original: {original_size_kb:.1f}KB)")
        image_base64 = compress_image_to_base64(file_path, max_size_kb=800)
        compressed_size_kb = len(image_base64) * 3 / 4 / 1024  # Approximate base64 size
        logger.info(f"Image compressed: {original_size_kb:.1f}KB → {compressed_size_kb:.1f}KB")

        # Perform AI analysis on the uploaded photo
        logger.info(f"Starting AI analysis for: {filename}")
        import time
        start_time = time.time()
        ai_analysis = analyze_uploaded_photo_with_ai(image_base64)
        analysis_time = time.time() - start_time

        confidence = ai_analysis.get('confidence', 0)
        logger.info(f"AI analysis complete in {analysis_time:.2f}s: {ai_analysis.get('item_name', 'Unknown')} (confidence: {confidence:.2f})")

        if confidence < 0.5:
            logger.warning(f"Low confidence identification ({confidence:.2f}): {ai_analysis.get('item_name', 'Unknown')}")

        # Prepare result with photo URL
        ai_result = {
            'item_name': ai_analysis['item_name'],
            'category': ai_analysis['category'],
            'description': ai_analysis['description'],
            'estimated_value_min': ai_analysis['estimated_value_min'],
            'estimated_value_max': ai_analysis['estimated_value_max'],
            'confidence': ai_analysis['confidence'],
            'photo_url': f'/static/uploads/{filename}'
        }

        # Automatically create the inventory item
        user = get_current_user()
        estate_id = get_current_estate_id()

        if not estate_id:
            return jsonify({
                'success': False,
                'error': 'No estate selected'
            }), 400

        # Create the item
        item_id = str(uuid.uuid4())
        avg_value = (ai_result['estimated_value_min'] + ai_result['estimated_value_max']) / 2

        item = {
            'id': item_id,
            'name': ai_result['item_name'],
            'category': ai_result['category'],
            'description': ai_result['description'],
            'value': avg_value,
            'photo': ai_result['photo_url'],
            'location': '',
            'assigned_to': '',
            'estate_id': estate_id,
            'created_at': datetime.now().isoformat(),
            'created_by': user.get('email', 'Unknown'),
            'upload_source': 'mobile'
        }

        # Save to Firestore
        storage_service.add_document('inventory', item_id, item)
        logger.info(f"Item created from hero upload: {item_id} - {item['name']}")

        # Log activity
        log_activity(estate_id, user.get('email', 'Unknown'), 'added', item_id, item['name'], {
            'category': item['category'],
            'value': item['value']
        })

        return jsonify({
            'success': True,
            'analysis': ai_result,
            'item': item,
            'message': 'Item added to inventory successfully'
        })
        
    except Exception as e:
        logger.error(f"Error in hero upload: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Upload failed'
        }), 500

@app.route('/api/qr/generate', methods=['POST'])
@require_auth
@limiter.limit("20 per hour")
def generate_qr():
    """Generate QR code for mobile upload"""
    try:
        # Generate unique upload session
        session_id = str(uuid.uuid4())

        # Store the current estate_id with this QR session so mobile uploads go to correct estate
        current_estate_id = get_current_estate_id()
        storage_service.add_document('qr_sessions', session_id, {
            'estate_id': current_estate_id,
            'created_at': datetime.now().isoformat()
        })
        logger.info(f"QR session {session_id} created for estate {current_estate_id}")

        # Create QR code with upload URL
        upload_url = f"{request.host_url}mobile-upload?session={session_id}"

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(upload_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()

        return jsonify({
            'success': True,
            'qr_code': f"data:image/png;base64,{img_str}",
            'upload_url': upload_url,
            'session_id': session_id
        })

    except Exception as e:
        logger.error(f"Error generating QR code: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate QR code'
        }), 500


@app.route('/api/qr/photo-session', methods=['POST'])
@require_auth
@limiter.limit("30 per hour")
def generate_photo_session_qr():
    """Generate QR for inline photo capture in Add Item modal — no item creation."""
    try:
        session_id = str(uuid.uuid4())
        current_estate_id = get_current_estate_id()
        storage_service.add_document('qr_sessions', session_id, {
            'estate_id': current_estate_id,
            'created_at': datetime.now().isoformat(),
            'mode': 'photo_only',
            'photo': None
        })
        upload_url = f"{request.host_url}mobile-upload?session={session_id}&mode=addphoto"
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(upload_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return jsonify({'success': True, 'qr_code': f"data:image/png;base64,{img_str}", 'session_id': session_id})
    except Exception as e:
        logger.error(f"Error generating photo-session QR: {e}")
        return jsonify({'success': False, 'error': 'Failed to generate QR code'}), 500


@app.route('/api/qr/photo-submit/<session_id>', methods=['POST'])
@limiter.limit("10 per hour")
def submit_photo_for_session(session_id):
    """Mobile uploads photo into a photo-only QR session (no item created)."""
    try:
        qr_session = storage_service.get_document('qr_sessions', session_id)
        if not qr_session:
            return jsonify({'success': False, 'error': 'Invalid or expired session'}), 400
        if qr_session.get('mode') != 'photo_only':
            return jsonify({'success': False, 'error': 'Invalid session mode'}), 400
        if 'photo' not in request.files:
            return jsonify({'success': False, 'error': 'No photo provided'}), 400
        file = request.files['photo']
        if not file.filename or not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'Invalid file type'}), 400
        filename = secure_filename(file.filename)
        upload_dir = '/tmp/uploads' if os.environ.get('GAE_ENV') else os.path.join(tempfile.gettempdir(), 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"qr_{session_id}_{filename}")
        file.save(file_path)
        photo_base64 = compress_image_to_base64(file_path, max_size_kb=150)
        storage_service.update_document('qr_sessions', session_id, {'photo': f"data:image/jpeg;base64,{photo_base64}"})
        logger.info(f"Photo stored for photo-only session {session_id}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error in photo-submit for session {session_id}: {e}")
        return jsonify({'success': False, 'error': 'Upload failed'}), 500


@app.route('/api/qr/photo-poll/<session_id>', methods=['GET'])
@require_auth
@limiter.limit("120 per hour")
def poll_photo_session(session_id):
    """Desktop polls here; returns photo and clears it once consumed."""
    try:
        qr_session = storage_service.get_document('qr_sessions', session_id)
        if not qr_session:
            return jsonify({'ready': False})
        if qr_session.get('mode') != 'photo_only':
            return jsonify({'ready': False})
        photo = qr_session.get('photo')
        if photo:
            storage_service.update_document('qr_sessions', session_id, {'photo': None})  # consume once
            return jsonify({'ready': True, 'photo': photo})
        return jsonify({'ready': False})
    except Exception as e:
        logger.error(f"Error polling photo session {session_id}: {e}")
        return jsonify({'ready': False}), 500


@app.route('/mobile-upload')
def mobile_upload():
    """Mobile upload page for QR code access"""
    session_id = request.args.get('session')
    if not session_id:
        return "Invalid session. Please scan the QR code again.", 400
    
    return render_template('mobile-upload.html', session_id=session_id)

@app.route('/api/mobile/upload', methods=['POST'])
def mobile_upload_api():
    """Handle mobile photo upload"""
    try:
        logger.info(f"Mobile upload request received. Files: {list(request.files.keys())}, Form data: {list(request.form.keys())}")
        
        if 'photo' not in request.files:
            logger.error("No photo file in request")
            return jsonify({
                'success': False,
                'error': 'No photo provided'
            }), 400
        
        file = request.files['photo']
        if file.filename == '':
            logger.error("Empty filename")
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400

        # Security: Validate file type
        if not allowed_file(file.filename):
            logger.error(f"Invalid file type: {file.filename}")
            return jsonify({
                'success': False,
                'error': 'Invalid file type. Allowed types: images (PNG, JPG, GIF, WebP, SVG) and documents (PDF)'
            }), 400

        session_id = request.form.get('session_id')
        if not session_id:
            logger.error("No session ID provided")
            return jsonify({
                'success': False,
                'error': 'Invalid session'
            }), 400
        
        logger.info(f"Processing upload for session {session_id}, filename: {file.filename}")
        
        # Save uploaded file (in production, use cloud storage)
        filename = secure_filename(file.filename)
        
        # For Google App Engine, use /tmp directory
        if os.environ.get('GAE_ENV'):
            upload_dir = '/tmp/uploads'
        else:
            upload_dir = os.path.join(tempfile.gettempdir(), 'uploads')
        
        try:
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)
            logger.info(f"File saved to: {file_path}")
        except Exception as file_error:
            logger.error(f"File save error: {file_error}")
            # Continue without file save for now
            file_path = None
        
        # Real AI analysis with OpenAI Vision API
        try:
            # Compress and convert uploaded image to base64 for storage
            photo_data = None
            if file_path and os.path.exists(file_path):
                try:
                    # Compress image for Firestore storage (max 800KB)
                    logger.info(f"Compressing image from: {file_path}")
                    photo_data = compress_image_to_base64(file_path, max_size_kb=800)
                    photo_url = f"data:image/jpeg;base64,{photo_data}"

                    size_kb = len(photo_data) / 1024
                    logger.info(f"Image compressed to base64, size: {size_kb:.2f}KB ({len(photo_data)} chars)")

                    # Compress smaller version for AI analysis (max 200KB) — faster API response
                    # This keeps the total request time under 60s App Engine timeout
                    logger.info(f"Compressing smaller image for AI analysis: {filename}")
                    ai_photo_data = compress_image_to_base64(file_path, max_size_kb=200, max_dimension=800)
                    ai_size_kb = len(ai_photo_data) / 1024
                    logger.info(f"AI image size: {ai_size_kb:.2f}KB")

                    # Perform AI analysis on the uploaded photo (using smaller image for speed)
                    # Use timeout to prevent App Engine 60-second timeout
                    logger.info(f"Starting AI analysis for mobile upload: {filename}")
                    import time
                    import signal

                    def timeout_handler(signum, frame):
                        raise TimeoutError("AI analysis took too long")

                    start_time = time.time()
                    ai_analysis = None
                    try:
                        # Set 45-second timeout to ensure response before 60s App Engine limit
                        signal.signal(signal.SIGALRM, timeout_handler)
                        signal.alarm(45)

                        ai_analysis = analyze_uploaded_photo_with_ai(ai_photo_data)

                        signal.alarm(0)  # Cancel the alarm
                        analysis_time = time.time() - start_time

                        confidence = ai_analysis.get('confidence', 0)
                        logger.info(f"AI analysis complete in {analysis_time:.2f}s: {ai_analysis.get('item_name', 'Unknown')} (confidence: {confidence:.2f})")

                        if confidence < 0.5:
                            logger.warning(f"Low confidence mobile identification ({confidence:.2f}): {ai_analysis.get('item_name', 'Unknown')}")
                    except (TimeoutError, Exception) as ai_timeout:
                        signal.alarm(0)  # Cancel the alarm
                        analysis_time = time.time() - start_time
                        logger.warning(f"AI analysis timeout or error after {analysis_time:.2f}s: {ai_timeout}. Using fallback.")
                        ai_analysis = None

                except Exception as img_error:
                    logger.error(f"Image compression or AI analysis error: {img_error}")
                    photo_url = '/static/placeholder-image.png'
                    # Use fallback if AI fails
                    ai_analysis = {
                        'item_name': 'Mobile Uploaded Item',
                        'category': 'General',
                        'description': 'Item uploaded from mobile device via QR code.',
                        'estimated_value_min': 10,
                        'estimated_value_max': 50,
                        'confidence': 0.0
                    }
            else:
                photo_url = '/static/placeholder-image.png'
                ai_analysis = {
                    'item_name': 'Mobile Uploaded Item',
                    'category': 'General',
                    'description': 'Item uploaded from mobile device.',
                    'estimated_value_min': 0,
                    'estimated_value_max': 0,
                    'confidence': 0.0
                }

            ai_result = {
                'item_name': ai_analysis['item_name'],
                'category': ai_analysis['category'],
                'description': ai_analysis['description'],
                'estimated_value_min': ai_analysis['estimated_value_min'],
                'estimated_value_max': ai_analysis['estimated_value_max'],
                'confidence': ai_analysis['confidence'],
                'photo_url': photo_url,
                'photo_data': photo_data,  # Store base64 data for persistence
                'session_id': session_id
            }
            logger.info(f"AI result created: {ai_result['item_name']} (confidence: {ai_result['confidence']})")
        except Exception as ai_error:
            logger.error(f"AI result creation error: {ai_error}")
            return jsonify({
                'success': False,
                'error': f'Failed to process image: {str(ai_error)}'
            }), 500
        
        # Get estate ID from the QR session — persisted in Firestore when the
        # QR code was generated. (Never use in-memory storage for this: App
        # Engine routes requests across instances, so memory does not survive.)
        estate_id = None
        qr_session = storage_service.get_document('qr_sessions', session_id)
        if qr_session:
            estate_id = qr_session.get('estate_id')
            logger.info(f"Using estate_id {estate_id} from QR session {session_id}")
        else:
            # Fallback: the uploading browser may itself be logged in
            estate_id = get_current_estate_id()
            logger.warning(f"QR session {session_id} not found in Firestore, current session estate_id: {estate_id}")

        if not estate_id:
            # Without an estate the item would be orphaned and invisible —
            # fail clearly instead
            return jsonify({
                'success': False,
                'error': 'This upload session has expired. Please generate a new QR code on your computer and scan it again.'
            }), 400

        # Add the item to inventory storage (like regular upload)
        try:
            item_id = str(uuid.uuid4())
            item = {
                'id': item_id,
                'estate_id': estate_id,  # Associate with estate if available
                'name': ai_result['item_name'],
                'category': ai_result['category'],
                'description': ai_result['description'],
                'estimatedValue': (ai_result['estimated_value_min'] + ai_result['estimated_value_max']) / 2,
                'forSale': False,  # Mobile uploads default to not for sale
                'assignedTo': '',  # Not assigned to anyone initially
                'photo': ai_result['photo_url'],
                'photo_data': ai_result.get('photo_data'),  # Store base64 image data
                'dateAdded': datetime.now().isoformat(),
                'lastModified': datetime.now().isoformat(),
                'uploadSource': 'mobile',  # Track that this came from mobile upload
                'sessionId': session_id
            }
            # Log without photo fields — the base64 blob is huge and floods logs
            logger.info(f"Item created: {item_id} '{item['name']}' (estate {estate_id})")
        except Exception as item_error:
            logger.error(f"Item creation error: {item_error}")
            return jsonify({
                'success': False,
                'error': f'Failed to create item: {str(item_error)}'
            }), 500
        
        # Store in inventory — Firestore is the system of record.
        # (The legacy JSON-file backup was removed in the Firestore migration;
        # referencing it here caused a NameError 500 on every mobile upload.)
        firestore_success = False
        try:
            # Check photo size before saving to Firestore (1MB document limit).
            # Images should already be compressed to ~800KB, but check as safety net.
            photo_data_size = len(item.get('photo_data', '')) if item.get('photo_data') else 0
            logger.info(f"Item photo_data size: {photo_data_size} bytes ({photo_data_size / 1024:.2f} KB)")

            if photo_data_size > 900000:  # 900KB safety margin
                logger.warning(f"Photo still too large for Firestore after compression ({photo_data_size / 1024:.2f} KB), saving without photo_data")
                item_for_firestore = {k: v for k, v in item.items() if k != 'photo_data'}
                firestore_success = firestore_add_inventory_item(item_for_firestore)
            else:
                firestore_success = firestore_add_inventory_item(item)

            if firestore_success:
                logger.info(f"Item saved to Firestore: {item_id}")
            else:
                logger.error(f"firestore_add_inventory_item returned False for item {item_id}")
        except Exception as firestore_error:
            logger.error(f"Firestore save failed with exception: {firestore_error}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

        if not firestore_success:
            return jsonify({
                'success': False,
                'error': 'Your photo was received but could not be saved. Please try again.'
            }), 500

        logger.info(f"Mobile upload complete: item {item_id} saved to estate {estate_id}")

        return jsonify({
            'success': True,
            'analysis': ai_result,
            'item': item,
            'message': 'Photo uploaded and added to inventory successfully! You can now close this page.'
        })
        
    except Exception as e:
        logger.error(f"Error in mobile upload: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': f'Upload failed: {str(e)}'
        }), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    try:
        # Security: Prevent path traversal attacks
        if '..' in filename or filename.startswith('/') or filename.startswith('\\'):
            logger.warning(f"Path traversal attempt blocked: {filename}")
            abort(404)

        # For Google App Engine, use /tmp/uploads
        if os.environ.get('GAE_ENV'):
            upload_dir = '/tmp/uploads'
        else:
            upload_dir = os.path.join(tempfile.gettempdir(), 'uploads')

        logger.info(f"Serving uploaded file: {filename} from {upload_dir}")

        if os.path.exists(os.path.join(upload_dir, filename)):
            return send_from_directory(upload_dir, filename)
        else:
            logger.warning(f"Uploaded file not found: {filename} in {upload_dir}")
            # Return a placeholder image instead of 404
            return send_from_directory('static', 'placeholder-image.png')
            
    except Exception as e:
        logger.error(f"Error serving uploaded file {filename}: {str(e)}")
        # Return a placeholder image instead of 404
        try:
            return send_from_directory('static', 'placeholder-image.png')
        except:
            return "Image not available", 404

# Family Sharing API Routes
@app.route('/api/family/invite', methods=['POST'])
@require_auth
@limiter.limit("10 per hour")
def invite_family_member():
    """Invite a family member to the current estate"""
    try:
        estate_id = get_current_estate_id()
        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        estate_data = get_family_estate_data(estate_id)

        data = request.get_json()
        email = data.get('email', '').strip().lower()
        name = data.get('name', '').strip()
        role = data.get('role', 'heir')  # executor, heir, viewer

        # Validate role
        valid_roles = ['executor', 'heir', 'viewer']
        if role not in valid_roles:
            role = 'heir'  # Default to heir if invalid

        if not email or not name:
            return jsonify({
                'success': False,
                'error': 'Email and name are required'
            }), 400

        # Check if already invited for this estate
        for member_code, member in estate_data['members'].items():
            if member['email'] == email:
                return jsonify({
                    'success': False,
                    'error': 'This email is already invited'
                }), 400

        # Generate member code
        member_code = generate_member_code(estate_data)
        if not member_code:
            return jsonify({
                'success': False,
                'error': 'Maximum number of family members reached (25)'
            }), 400

        # Add family member
        estate_data['members'][member_code] = {
            'email': email,
            'name': name,
            'role': role,
            'status': 'invited',
            'invited_at': datetime.now().isoformat(),
            'last_active': None
        }

        # Find existing active share link
        share_id = None
        for sid, link in estate_data['share_links'].items():
            expires_at = datetime.fromisoformat(link['expires_at'])
            if link.get('active', True) and datetime.now() < expires_at:
                share_id = sid
                break

        if not share_id:
            share_id = generate_share_link(estate_id)
        # Data already persisted by generate_share_link or get_family_estate_data

        return jsonify({
            'success': True,
            'message': 'Family member invited successfully',
            'member_code': member_code,
            'share_link': f"{request.host_url}family-view?share={share_id}"
        })

    except Exception as e:
        logger.error(f"Error inviting family member: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to invite family member'
        }), 500

# ============================================================================
# FAMILY ROLES & PERMISSIONS
# ============================================================================

def get_user_role_in_estate(user_id, estate_id):
    """Get the user's role in an estate (owner, executor, heir, viewer)"""
    try:
        # Check if user is the estate owner
        estates = storage_service.list_documents('estates')
        for estate in estates:
            if estate.get('id') == estate_id and estate.get('owner_id') == user_id:
                return 'owner'  # Estate owner has full control

        # Check family member role
        estate_data = get_family_estate_data(estate_id)
        for member_code, member in estate_data['members'].items():
            if member.get('email') == session.get('user_email'):
                return member.get('role', 'viewer')

        return None  # Not a member of this estate
    except Exception as e:
        logger.error(f"Error getting user role: {e}")
        return None

def check_permission(user_id, estate_id, required_permission):
    """Check if user has required permission for an action"""
    role = get_user_role_in_estate(user_id, estate_id)

    permissions = {
        'owner': ['view', 'edit', 'delete', 'manage_members', 'manage_roles'],
        'executor': ['view', 'edit', 'manage_members'],
        'heir': ['view', 'mark_wants'],
        'viewer': ['view']
    }

    return role and required_permission in permissions.get(role, [])

@app.route('/api/family/members', methods=['GET'])
@require_auth
def get_family_members():
    """Get all family members for the current estate"""
    try:
        estate_id = get_current_estate_id()
        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        estate_data = get_family_estate_data(estate_id)

        members = []
        for member_code, member in estate_data['members'].items():
            members.append({
                'code': member_code,
                'name': member['name'],
                'email': member['email'],
                'role': member.get('role', 'heir'),  # Default to heir for existing members
                'status': member['status'],
                'invited_at': member['invited_at'],
                'last_active': member['last_active']
            })

        return jsonify({
            'success': True,
            'members': members,
            'total_members': len(members),
            'max_members': estate_data['sharing_settings']['max_members']
        })

    except Exception as e:
        logger.error(f"Error getting family members: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get family members'
        }), 500

@app.route('/api/family/members/<member_code>/role', methods=['PUT'])
@require_auth
def update_member_role(member_code):
    """Update a family member's role"""
    try:
        user_id = session.get('user_id')
        estate_id = get_current_estate_id()

        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        # Check if user has permission to manage roles (only owner and executors)
        if not check_permission(user_id, estate_id, 'manage_roles') and \
           not check_permission(user_id, estate_id, 'manage_members'):
            return jsonify({
                'success': False,
                'error': 'You do not have permission to manage roles'
            }), 403

        data = request.get_json()
        new_role = data.get('role', '').lower()

        # Validate role
        valid_roles = ['executor', 'heir', 'viewer']
        if new_role not in valid_roles:
            return jsonify({
                'success': False,
                'error': f'Invalid role. Must be one of: {", ".join(valid_roles)}'
            }), 400

        estate_data = get_family_estate_data(estate_id)

        # Check if member exists
        if member_code not in estate_data['members']:
            return jsonify({
                'success': False,
                'error': 'Family member not found'
            }), 404

        # Update role
        estate_data['members'][member_code]['role'] = new_role

        # Save changes to Firestore
        firestore_update_family_data(estate_id, {'members': estate_data['members']})

        return jsonify({
            'success': True,
            'message': f'Role updated to {new_role}',
            'member': {
                'code': member_code,
                'name': estate_data['members'][member_code]['name'],
                'role': new_role
            }
        })

    except Exception as e:
        logger.error(f"Error updating member role: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to update role'
        }), 500

@app.route('/api/family/want-item/<share_id>', methods=['POST'])
def want_item(share_id):
    """Add or remove item from wanted list"""
    try:
        estate_id, estate_data, share_link = get_share_link_context(share_id)
        if not estate_id or not share_link:
            return jsonify({'success': False, 'error': 'Invalid or expired share link'}), 404

        # Ensure share link is active and not expired
        if not share_link.get('active', True):
            return jsonify({'success': False, 'error': 'Share link inactive'}), 403

        expires_at = datetime.fromisoformat(share_link['expires_at'])
        if datetime.now() > expires_at:
            share_link['active'] = False
            # Update share link in Firestore
            firestore_update_share_link(share_id, {'active': False})
            estate_data['share_links'][share_id]['active'] = False
            firestore_update_family_data(estate_id, {'share_links': estate_data['share_links']})
            return jsonify({'success': False, 'error': 'Share link expired'}), 403

        data = request.get_json()
        item_id = data.get('item_id')
        member_code = data.get('member_code')
        action = data.get('action', 'add')  # 'add' or 'remove'
        priority = data.get('priority', 'medium')

        if not item_id or not member_code:
            return jsonify({
                'success': False,
                'error': 'Item ID and member code are required'
            }), 400

        # Verify member code exists for this estate
        if member_code not in estate_data['members']:
            return jsonify({
                'success': False,
                'error': 'Invalid member code'
            }), 400

        # Verify item exists and belongs to estate
        item = inventory_storage.get(item_id)
        if not item or item.get('estate_id') != estate_id:
            return jsonify({
                'success': False,
                'error': 'Item not found'
            }), 404

        # Initialize wanted items for member if not exists
        if member_code not in estate_data['wanted_items']:
            estate_data['wanted_items'][member_code] = []

        wanted_items = estate_data['wanted_items'][member_code]

        if action == 'add':
            # Check if already wanted
            existing_wanted = next((w for w in wanted_items if w['item_id'] == item_id), None)
            if not existing_wanted:
                wanted_items.append({
                    'item_id': item_id,
                    'priority': priority,
                    'desire_level': data.get('desire_level', 3),  # Default to level 3
                    'wanted_at': datetime.now().isoformat()
                })
                message = 'Item added to wanted list'
            else:
                # Update existing entry
                existing_wanted['priority'] = priority
                existing_wanted['desire_level'] = data.get('desire_level', existing_wanted.get('desire_level', 3))
                existing_wanted['wanted_at'] = datetime.now().isoformat()
                message = 'Item desire level updated'
        else:  # remove
            estate_data['wanted_items'][member_code] = [
                w for w in wanted_items if w['item_id'] != item_id
            ]
            message = 'Item removed from wanted list'

        # Update member last active
        estate_data['members'][member_code]['last_active'] = datetime.now().isoformat()
        estate_data['members'][member_code]['status'] = 'active'

        # Save changes to Firestore
        firestore_update_family_data(estate_id, {
            'wanted_items': estate_data['wanted_items'],
            'members': estate_data['members']
        })

        return jsonify({
            'success': True,
            'message': message
        })

    except Exception as e:
        logger.error(f"Error updating wanted item: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to update wanted item'
        }), 500

@app.route('/api/family/wanted-items/<share_id>/<member_code>', methods=['GET'])
def get_wanted_items(share_id, member_code):
    """Get wanted items for a family member"""
    try:
        estate_id, estate_data, share_link = get_share_link_context(share_id)
        if not estate_id or not share_link:
            return jsonify({'success': False, 'error': 'Invalid or expired share link'}), 404

        if member_code not in estate_data['members']:
            return jsonify({
                'success': False,
                'error': 'Invalid member code'
            }), 400

        wanted_items = estate_data['wanted_items'].get(member_code, [])

        return jsonify({
            'success': True,
            'wanted_items': wanted_items
        })

    except Exception as e:
        logger.error(f"Error getting wanted items: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get wanted items'
        }), 500

@app.route('/api/family/shared-inventory/<share_id>', methods=['GET'])
def get_shared_inventory_api(share_id):
    """Get shared inventory for family members"""
    try:
        inventory = get_shared_inventory(share_id)
        
        if inventory is None:
            return jsonify({
                'success': False,
                'error': 'Invalid or expired sharing link'
            }), 404
        
        return jsonify({
            'success': True,
            'inventory': inventory
        })
        
    except Exception as e:
        logger.error(f"Error getting shared inventory: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get shared inventory'
        }), 500

@app.route('/api/family/settings', methods=['GET', 'POST'])
@require_auth
def family_settings():
    """Get or update family sharing settings for current estate"""
    try:
        estate_id = get_current_estate_id()
        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        estate_data = get_family_estate_data(estate_id)

        if request.method == 'GET':
            return jsonify({
                'success': True,
                'settings': estate_data['sharing_settings']
            })

        # POST - update settings
        data = request.get_json()

        if 'show_for_sale_only' in data:
            estate_data['sharing_settings']['show_for_sale_only'] = bool(data['show_for_sale_only'])

        if 'allow_wanted_tagging' in data:
            estate_data['sharing_settings']['allow_wanted_tagging'] = bool(data['allow_wanted_tagging'])

        # Save changes to Firestore
        firestore_update_family_data(estate_id, {'sharing_settings': estate_data['sharing_settings']})

        return jsonify({
            'success': True,
            'message': 'Settings updated successfully',
            'settings': estate_data['sharing_settings']
        })

    except Exception as e:
        logger.error(f"Error handling family settings: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to handle family settings'
        }), 500

@app.route('/api/family/share-link', methods=['GET', 'POST'])
@require_auth
def manage_share_link():
    """Get or regenerate family sharing link for current estate"""
    try:
        estate_id = get_current_estate_id()
        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        estate_data = get_family_estate_data(estate_id)

        if request.method == 'GET':
            # Get existing active link for this estate
            for share_id, link in estate_data['share_links'].items():
                expires_at = datetime.fromisoformat(link['expires_at'])
                if link.get('active', True) and datetime.now() < expires_at:
                    family_storage['share_links'][share_id] = link
                    return jsonify({
                        'success': True,
                        'share_link': f"{request.host_url}family-view?share={share_id}",
                        'share_id': share_id,
                        'created_at': link['created_at'],
                        'expires_at': link['expires_at']
                    })

            return jsonify({
                'success': False,
                'error': 'No active sharing link found'
            }), 404

        # POST - generate new link
        share_id = generate_share_link(estate_id)

        return jsonify({
            'success': True,
            'message': 'New sharing link generated',
            'share_link': f"{request.host_url}family-view?share={share_id}",
            'share_id': share_id
        })

    except Exception as e:
        logger.error(f"Error managing share link: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to manage share link'
        }), 500

# Error handlers
# ===== AUTHENTICATION ENDPOINTS =====

# Email check endpoint for progressive auth
@app.route('/api/auth/check-email', methods=['POST'])
@limiter.limit("10 per minute")
def check_email():
    """Check if email exists in the system"""
    try:
        data = request.get_json()
        email = data.get('email', '').lower().strip()

        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400

        # Check if user exists (Firestore or JSON)
        exists = False
        if USE_FIRESTORE:
            user = firestore_get_user_by_email(email)
            exists = user is not None
        else:
            exists = any(user.get('email') == email for user in auth_storage['users'].values())

        return jsonify({
            'success': True,
            'exists': exists
        })

    except Exception as e:
        logger.error(f"Error checking email: {str(e)}")
        return jsonify({'success': False, 'error': 'Email check failed'}), 500

# MFA verification endpoint
@app.route('/api/auth/verify-mfa', methods=['POST'])
@limiter.limit("5 per minute")  # Prevent MFA brute force
def verify_mfa():
    """Verify MFA code during login"""
    try:
        import pyotp
        
        data = request.get_json()
        code = data.get('code', '')
        session_id = data.get('session_id', '')
        trust_device = data.get('trust_device', False)
        
        if not code or not session_id:
            return jsonify({'success': False, 'error': 'Code and session ID required'}), 400
        
        # Get session data
        if session_id not in auth_storage.get('mfa_sessions', {}):
            return jsonify({'success': False, 'error': 'Invalid or expired session'}), 401

        mfa_session = auth_storage['mfa_sessions'][session_id]
        user_id = mfa_session.get('user_id')

        # Get user (Firestore or JSON)
        user = None
        if USE_FIRESTORE:
            user = firestore_get_user(user_id)
        else:
            user = auth_storage['users'].get(user_id)

        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 401
        
        # Verify TOTP code
        mfa_secret = user.get('mfa_secret')
        if not mfa_secret:
            return jsonify({'success': False, 'error': 'MFA not enabled'}), 401
        
        totp = pyotp.TOTP(mfa_secret)
        if not totp.verify(code, valid_window=1):
            return jsonify({'success': False, 'error': 'Invalid code'}), 401
        
        # MFA successful - create session
        session['user_id'] = user_id
        session['user_email'] = user['email']
        
        if trust_device:
            session['mfa_trusted'] = True
            session.permanent = True
        
        # Clean up MFA session
        del auth_storage['mfa_sessions'][session_id]
        
        return jsonify({
            'success': True,
            'user': {
                'id': user_id,
                'email': user['email'],
                'name': user['name'],
                'provider': user['provider']
            }
        })
        
    except Exception as e:
        logger.error(f"MFA verification error: {str(e)}")
        return jsonify({'success': False, 'error': 'MFA verification failed'}), 500

# MFA setup verification endpoint
@app.route('/api/auth/verify-mfa-setup', methods=['POST'])
@limiter.limit("5 per minute")
def verify_mfa_setup():
    """Verify MFA setup during account creation"""
    try:
        import pyotp
        
        data = request.get_json()
        code = data.get('code', '')
        secret = data.get('secret', '')
        session_id = data.get('session_id', '')
        
        if not code or not secret:
            return jsonify({'success': False, 'error': 'Code and secret required'}), 400
        
        # Verify TOTP code
        totp = pyotp.TOTP(secret)
        if not totp.verify(code, valid_window=1):
            return jsonify({'success': False, 'error': 'Invalid code. Please try again.'}), 401
        
        # Get user from session
        if session_id and session_id in auth_storage.get('mfa_sessions', {}):
            user_id = auth_storage['mfa_sessions'][session_id]['user_id']

            # Get user from Firestore or JSON
            if USE_FIRESTORE:
                user = firestore_get_user(user_id)
            else:
                user = auth_storage['users'].get(user_id)

            if user:
                # Save MFA secret to user
                user['mfa_secret'] = secret
                user['mfa_enabled'] = True

                # Update in Firestore or JSON
                if USE_FIRESTORE:
                    firestore_update_user(user_id, {
                        'mfa_secret': secret,
                        'mfa_enabled': True
                    })
                else:
                    auth_storage['users'][user_id] = user
                    save_auth_storage()

                # Create session
                session['user_id'] = user_id
                session['user_email'] = user['email']

                # Clean up MFA session
                del auth_storage['mfa_sessions'][session_id]

                return jsonify({
                    'success': True,
                    'user': {
                        'id': user_id,
                        'email': user['email'],
                        'name': user['name'],
                        'provider': user.get('provider', 'email')
                    }
                })

        return jsonify({'success': False, 'error': 'Session not found'}), 401
        
    except Exception as e:
        logger.error(f"MFA setup verification error: {str(e)}")
        return jsonify({'success': False, 'error': 'MFA setup verification failed'}), 500

@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("5 per minute")  # Prevent brute force attacks
def login():
    """Handle email/password login"""
    try:
        data = request.get_json()

        # Validate required fields
        valid, error = validate_required_fields(data, ['email', 'password'])
        if not valid:
            return jsonify({'success': False, 'error': error}), 400

        email = sanitize_string(data.get('email')).lower().strip()
        password = data.get('password', '')

        # Validate email format
        if not validate_email(email):
            return jsonify({
                'success': False,
                'error': 'Invalid email format'
            }), 400

        if len(password) > 128:  # Reasonable password length limit
            return jsonify({
                'success': False,
                'error': 'Password too long'
            }), 400
        
        # Find user by email (Firestore or JSON)
        user = None
        if USE_FIRESTORE:
            user = firestore_get_user_by_email(email)
        else:
            for user_id, user_data in auth_storage['users'].items():
                if user_data.get('email') == email:
                    user = user_data
                    user['id'] = user_id
                    break

        if not user:
            return jsonify({
                'success': False,
                'error': 'Invalid email or password'
            }), 401

        # Verify password
        if not verify_password(password, user.get('password_hash', '')):
            return jsonify({
                'success': False,
                'error': 'Invalid email or password'
            }), 401
        
        # Check if MFA is enabled and device is not trusted
        if user.get('mfa_enabled') and not session.get('mfa_trusted'):
            # Create temporary MFA session
            if 'mfa_sessions' not in auth_storage:
                auth_storage['mfa_sessions'] = {}
            
            mfa_session_id = secrets.token_urlsafe(32)
            auth_storage['mfa_sessions'][mfa_session_id] = {
                'user_id': user['id'],
                'created_at': datetime.now().isoformat(),
                'expires_at': (datetime.now() + timedelta(minutes=5)).isoformat()
            }
            
            return jsonify({
                'success': True,
                'mfa_required': True,
                'session_id': mfa_session_id,
                'message': 'MFA verification required'
            })
        
        # Update last login
        user['last_login'] = datetime.now().isoformat()
        if USE_FIRESTORE:
            firestore_update_user(user['id'], {'last_login': user['last_login']})
        else:
            auth_storage['users'][user['id']] = user
            save_auth_storage()
        
        # Create session
        session['user_id'] = user['id']
        session['user_email'] = user['email']
        
        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'email': user['email'],
                'name': user['name'],
                'provider': user['provider'],
                'created_at': user['created_at'],
                'last_login': user['last_login']
            },
            'message': 'Login successful'
        })
        
    except Exception as e:
        logger.error(f"Error in login: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Login failed'
        }), 500

@app.route('/api/auth/signup', methods=['POST'])
@limiter.limit("3 per hour")  # Prevent spam account creation
def signup():
    """Handle email/password signup"""
    try:
        data = request.get_json()

        # Validate required fields
        valid, error = validate_required_fields(data, ['email', 'password'])
        if not valid:
            return jsonify({'success': False, 'error': error}), 400

        email = sanitize_string(data.get('email')).lower().strip()
        password = data.get('password', '')
        name = sanitize_string(data.get('name', '').strip(), max_length=100)
        beta_code = sanitize_string(data.get('beta_code', '').strip(), max_length=50)

        # Validate email format
        if not validate_email(email):
            return jsonify({
                'success': False,
                'error': 'Invalid email format'
            }), 400

        # Validate password strength (OWASP recommendations)
        password_valid, password_error = validate_password_strength(password)
        if not password_valid:
            return jsonify({
                'success': False,
                'error': password_error
            }), 400

        # Check if user already exists (Firestore or JSON)
        if USE_FIRESTORE:
            existing_user = firestore_get_user_by_email(email)
            if existing_user:
                return jsonify({
                    'success': False,
                    'error': 'User with this email already exists'
                }), 400
        else:
            for user_id, user_data in auth_storage['users'].items():
                if user_data.get('email') == email:
                    return jsonify({
                        'success': False,
                        'error': 'User with this email already exists'
                    }), 400

        # Determine account type based on beta code
        BETA_CODE = os.environ.get('BETA_CODE') or get_secret('BETA_CODE') or 'ESTATEALLY2026'
        account_type = 'beta' if beta_code == BETA_CODE else 'free'
        grandfathered = (account_type == 'beta')

        # Check if MFA should be enabled
        enable_mfa = data.get('enable_mfa', False)

        # Create new user with account_type field
        user_id = generate_user_id()
        user_data = {
            'id': user_id,
            'email': email,
            'name': name or email.split('@')[0].title(),
            'provider': 'email',
            'password_hash': hash_password(password),
            'created_at': datetime.now().isoformat(),
            'last_login': datetime.now().isoformat(),
            'mfa_enabled': False,
            'account_type': account_type,
            'grandfathered': grandfathered,
            'stripe_customer_id': None
        }

        # Save to Firestore or JSON
        if USE_FIRESTORE:
            firestore_add_user(user_data)
        else:
            auth_storage['users'][user_id] = user_data
            save_auth_storage()
        
        # If MFA requested, generate secret and return it
        if enable_mfa:
            import pyotp
            mfa_secret = pyotp.random_base32()
            
            # Create temporary MFA session
            if 'mfa_sessions' not in auth_storage:
                auth_storage['mfa_sessions'] = {}
            
            mfa_session_id = secrets.token_urlsafe(32)
            auth_storage['mfa_sessions'][mfa_session_id] = {
                'user_id': user_id,
                'created_at': datetime.now().isoformat(),
                'expires_at': (datetime.now() + timedelta(minutes=10)).isoformat()
            }
            
            return jsonify({
                'success': True,
                'mfa_required': True,
                'mfa_secret': mfa_secret,
                'session_id': mfa_session_id,
                'message': 'Please set up two-factor authentication'
            })
        
        # Create session (if no MFA)
        session['user_id'] = user_id
        session['user_email'] = email
        
        return jsonify({
            'success': True,
            'user': {
                'id': user_id,
                'email': user_data['email'],
                'name': user_data['name'],
                'provider': user_data['provider'],
                'created_at': user_data['created_at'],
                'last_login': user_data['last_login']
            },
            'message': 'Account created successfully'
        })
        
    except Exception as e:
        logger.error(f"Error in signup: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Signup failed'
        }), 500

@app.route('/reset-password')
def reset_password_page():
    """Serve the app at /reset-password so JS can read ?token= from URL"""
    return render_template('index.html')


@app.route('/api/auth/forgot-password', methods=['POST'])
@limiter.limit("3 per hour")
def forgot_password():
    """Send a password reset email with a time-limited token"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': True})  # Don't leak info

        email = data.get('email', '').strip().lower()
        if not email:
            return jsonify({'success': True})  # Don't leak info

        # Look up user by email
        user = firestore_get_user_by_email(email)

        # Only send reset for email/password accounts (not OAuth)
        if user and user.get('provider', 'email') == 'email':
            user_id = user['id']
            token = secrets.token_urlsafe(32)
            expires_at = (datetime.now() + timedelta(hours=1)).isoformat()

            # Store token in Firestore
            if USE_FIRESTORE and db:
                db.collection('password_resets').document(token).set({
                    'user_id': user_id,
                    'email': email,
                    'expires_at': expires_at,
                    'created_at': datetime.now().isoformat()
                })
            else:
                auth_storage['password_resets'][token] = {
                    'user_id': user_id,
                    'email': email,
                    'expires_at': expires_at
                }

            # Build reset URL
            base_url = os.environ.get('APP_BASE_URL', 'https://estateally-ai-services.ue.r.appspot.com')
            reset_url = f"{base_url}/reset-password?token={token}"

            # Send email
            try:
                msg = Message(
                    subject='Reset your MyEstateAlly password',
                    recipients=[email],
                    html=f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                        <div style="background: #2563eb; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
                            <h1 style="color: white; margin: 0; font-size: 24px;">🏠 MyEstateAlly</h1>
                        </div>
                        <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; border: 1px solid #e5e7eb;">
                            <h2 style="color: #1f2937; margin-top: 0;">Reset Your Password</h2>
                            <p style="color: #4b5563;">We received a request to reset the password for your MyEstateAlly account.</p>
                            <p style="color: #4b5563;">Click the button below to set a new password. This link is valid for <strong>1 hour</strong>.</p>
                            <div style="text-align: center; margin: 30px 0;">
                                <a href="{reset_url}" style="background: #2563eb; color: white; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 16px;">Reset My Password</a>
                            </div>
                            <p style="color: #6b7280; font-size: 14px;">If you didn't request a password reset, you can safely ignore this email. Your password won't change.</p>
                            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
                            <p style="color: #9ca3af; font-size: 12px; text-align: center;">MyEstateAlly · Your AI-Powered Estate Management Partner</p>
                        </div>
                    </div>
                    """,
                    body=f"Reset your MyEstateAlly password by visiting: {reset_url}\n\nThis link expires in 1 hour.\n\nIf you didn't request this, ignore this email."
                )
                mail.send(msg)
                logger.info(f"Password reset email sent to {email}")
            except Exception as mail_err:
                # Log but don't fail — token is stored, user can retry
                logger.warning(f"Password reset email failed to send: {mail_err}. Reset URL: {reset_url}")

        # Always return success (prevent email enumeration)
        return jsonify({'success': True, 'message': 'If that email is registered, you will receive a reset link shortly.'})

    except Exception as e:
        logger.error(f"Error in forgot_password: {e}")
        return jsonify({'success': True})  # Don't leak errors


@app.route('/api/auth/reset-password', methods=['POST'])
@limiter.limit("5 per hour")
def reset_password_submit():
    """Validate a reset token and update the user's password"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid request'}), 400

        token = data.get('token', '').strip()
        new_password = data.get('new_password', '')

        if not token or not new_password:
            return jsonify({'success': False, 'error': 'Token and new password are required'}), 400

        # Look up token
        token_data = None
        if USE_FIRESTORE and db:
            doc = db.collection('password_resets').document(token).get()
            if doc.exists:
                token_data = doc.to_dict()
        else:
            token_data = auth_storage['password_resets'].get(token)

        if not token_data:
            return jsonify({'success': False, 'error': 'Invalid or expired reset link'}), 400

        # Check expiry
        expires_at = datetime.fromisoformat(token_data['expires_at'])
        if datetime.now() > expires_at:
            # Clean up expired token
            if USE_FIRESTORE and db:
                db.collection('password_resets').document(token).delete()
            else:
                auth_storage['password_resets'].pop(token, None)
            return jsonify({'success': False, 'error': 'This reset link has expired. Please request a new one.'}), 400

        # Validate password strength
        from src.utils.validation import validate_password_strength
        is_valid, pw_error = validate_password_strength(new_password)
        if not is_valid:
            return jsonify({'success': False, 'error': pw_error}), 400

        # Update password
        user_id = token_data['user_id']
        new_hash = hash_password(new_password)
        firestore_update_user(user_id, {'password_hash': new_hash})

        # Delete used token (single-use)
        if USE_FIRESTORE and db:
            db.collection('password_resets').document(token).delete()
        else:
            auth_storage['password_resets'].pop(token, None)

        logger.info(f"Password reset successful for user {user_id}")
        return jsonify({'success': True, 'message': 'Password reset successfully. Please sign in with your new password.'})

    except Exception as e:
        logger.error(f"Error in reset_password_submit: {e}")
        return jsonify({'success': False, 'error': 'Reset failed. Please try again.'}), 500


@app.route('/api/auth/google', methods=['GET'])
def google_auth():
    """Initiate Google OAuth flow"""
    try:
        state = secrets.token_urlsafe(32)
        auth_storage['oauth_states'][state] = {
            'provider': 'google',
            'created_at': datetime.now().isoformat()
        }
        
        # Google OAuth URL
        google_auth_url = (
            f"https://accounts.google.com/o/oauth2/auth?"
            f"client_id={OAUTH_CONFIG['google']['client_id']}&"
            f"redirect_uri={OAUTH_CONFIG['google']['redirect_uri']}&"
            f"scope=openid email profile&"
            f"response_type=code&"
            f"state={state}"
        )
        
        return jsonify({
            'success': True,
            'auth_url': google_auth_url,
            'state': state
        })
        
    except Exception as e:
        logger.error(f"Error in Google auth: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Google authentication failed'
        }), 500

@app.route('/api/auth/facebook', methods=['GET'])
def facebook_auth():
    """Initiate Facebook OAuth flow"""
    try:
        state = secrets.token_urlsafe(32)
        auth_storage['oauth_states'][state] = {
            'provider': 'facebook',
            'created_at': datetime.now().isoformat()
        }
        
        # Facebook OAuth URL
        facebook_auth_url = (
            f"https://www.facebook.com/v18.0/dialog/oauth?"
            f"client_id={OAUTH_CONFIG['facebook']['client_id']}&"
            f"redirect_uri={OAUTH_CONFIG['facebook']['redirect_uri']}&"
            f"scope=email&"
            f"response_type=code&"
            f"state={state}"
        )
        
        return jsonify({
            'success': True,
            'auth_url': facebook_auth_url,
            'state': state
        })
        
    except Exception as e:
        logger.error(f"Error in Facebook auth: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Facebook authentication failed'
        }), 500

@app.route('/api/auth/demo', methods=['POST'])
@limiter.limit("5 per hour")
def demo_login():
    """Create a demo user session"""
    try:
        user_id = 'demo-user-' + str(uuid.uuid4())[:8]
        user_data = {
            'id': user_id,
            'email': 'demo@myestateally.com',
            'name': 'Demo User',
            'provider': 'demo',
            'created_at': datetime.now().isoformat(),
            'last_login': datetime.now().isoformat()
        }
        
        auth_storage['users'][user_id] = user_data
        session_id = create_user_session(user_id)
        
        return jsonify({
            'success': True,
            'user': user_data,
            'session_id': session_id,
            'message': 'Demo login successful'
        })
        
    except Exception as e:
        logger.error(f"Error in demo login: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Demo login failed'
        }), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Handle user logout"""
    try:
        # Clear Flask session
        session.clear()
        
        return jsonify({
            'success': True,
            'message': 'Logout successful'
        })
        
    except Exception as e:
        logger.error(f"Error in logout: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Logout failed'
        }), 500

@app.route('/api/auth/verify', methods=['POST'])
def verify_session():
    """Verify user session"""
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'Session ID required'
            }), 400
        
        user = get_user_from_session(session_id)
        if not user:
            return jsonify({
                'success': False,
                'error': 'Invalid or expired session'
            }), 401
        
        return jsonify({
            'success': True,
            'user': user,
            'message': 'Session valid'
        })
        
    except Exception as e:
        logger.error(f"Error in session verification: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Session verification failed'
        }), 500

@app.route('/api/csrf-token', methods=['GET'])
def get_csrf_token():
    """Get CSRF token for client-side requests"""
    return jsonify({
        'success': True,
        'csrf_token': generate_csrf()
    })

# ===== USER PROFILE MANAGEMENT ENDPOINTS =====

@app.route('/api/user/profile', methods=['GET'])
@require_auth
def get_user_profile():
    """Get current user profile information"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404

        # Return safe user data (exclude sensitive fields)
        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'email': user['email'],
                'name': user['name'],
                'provider': user.get('provider', 'email'),
                'account_type': user.get('account_type', 'free'),
                'grandfathered': user.get('grandfathered', False),
                'created_at': user.get('created_at', ''),
                'last_login': user.get('last_login', ''),
                'mfa_enabled': user.get('mfa_enabled', False)
            }
        })
    except Exception as e:
        logger.error(f"Error fetching user profile: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to load profile'
        }), 500

@app.route('/api/user/profile', methods=['PUT'])
@require_auth
@limiter.limit("10 per minute")
def update_user_profile():
    """Update user profile information"""
    try:
        data = request.get_json()
        user = get_current_user()

        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404

        # Only allow updating name
        if 'name' not in data:
            return jsonify({
                'success': False,
                'error': 'No updates provided'
            }), 400

        new_name = sanitize_string(data['name'], max_length=100)

        if not new_name or len(new_name) < 2:
            return jsonify({
                'success': False,
                'error': 'Name must be at least 2 characters'
            }), 400

        # Update user
        user_id = session['user_id']
        if USE_FIRESTORE:
            firestore_update_user(user_id, {'name': new_name})
        else:
            auth_storage['users'][user_id]['name'] = new_name
            save_auth_storage()

        return jsonify({
            'success': True,
            'message': 'Profile updated successfully',
            'user': {
                'id': user_id,
                'name': new_name,
                'email': user['email']
            }
        })

    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to update profile'
        }), 500

@app.route('/api/user/change-password', methods=['POST'])
@require_auth
@limiter.limit("5 per minute")
def change_password():
    """Change user password"""
    try:
        data = request.get_json()
        user = get_current_user()

        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404

        # Only allow for email/password users
        if user.get('provider') != 'email':
            return jsonify({
                'success': False,
                'error': 'Password change not available for OAuth accounts'
            }), 400

        # Validate required fields
        valid, error = validate_required_fields(data, ['current_password', 'new_password'])
        if not valid:
            return jsonify({'success': False, 'error': error}), 400

        current_password = data['current_password']
        new_password = data['new_password']

        # Verify current password
        if not verify_password(current_password, user.get('password_hash', '')):
            return jsonify({
                'success': False,
                'error': 'Current password is incorrect'
            }), 401

        # Validate new password
        if len(new_password) < 8:
            return jsonify({
                'success': False,
                'error': 'New password must be at least 8 characters'
            }), 400

        if len(new_password) > 128:
            return jsonify({
                'success': False,
                'error': 'Password too long'
            }), 400

        # Hash new password
        new_password_hash = hash_password(new_password)

        # Update password
        user_id = session['user_id']
        if USE_FIRESTORE:
            firestore_update_user(user_id, {'password_hash': new_password_hash})
        else:
            auth_storage['users'][user_id]['password_hash'] = new_password_hash
            save_auth_storage()

        return jsonify({
            'success': True,
            'message': 'Password changed successfully'
        })

    except Exception as e:
        logger.error(f"Error changing password: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to change password'
        }), 500

@app.route('/api/user/toggle-mfa', methods=['POST'])
@require_auth
@limiter.limit("5 per minute")
def toggle_mfa():
    """Enable or disable MFA for user account"""
    try:
        import pyotp
        import qrcode
        import io
        import base64

        data = request.get_json()
        user = get_current_user()

        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404

        action = data.get('action')  # 'enable' or 'disable' or 'verify_enable'

        if action == 'enable':
            # Generate MFA secret
            mfa_secret = pyotp.random_base32()

            # Generate QR code
            totp = pyotp.TOTP(mfa_secret)
            provisioning_uri = totp.provisioning_uri(
                name=user['email'],
                issuer_name='MyEstateAlly'
            )

            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(provisioning_uri)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()

            return jsonify({
                'success': True,
                'action': 'setup',
                'mfa_secret': mfa_secret,
                'qr_code': f'data:image/png;base64,{qr_code_base64}',
                'message': 'Scan QR code with your authenticator app'
            })

        elif action == 'verify_enable':
            # Verify MFA code before enabling
            mfa_secret = data.get('mfa_secret')
            verification_code = data.get('code')

            if not mfa_secret or not verification_code:
                return jsonify({
                    'success': False,
                    'error': 'Missing verification data'
                }), 400

            totp = pyotp.TOTP(mfa_secret)
            if not totp.verify(verification_code, valid_window=1):
                return jsonify({
                    'success': False,
                    'error': 'Invalid verification code'
                }), 400

            # Enable MFA
            user_id = session['user_id']
            if USE_FIRESTORE:
                firestore_update_user(user_id, {
                    'mfa_enabled': True,
                    'mfa_secret': mfa_secret
                })
            else:
                auth_storage['users'][user_id]['mfa_enabled'] = True
                auth_storage['users'][user_id]['mfa_secret'] = mfa_secret
                save_auth_storage()

            return jsonify({
                'success': True,
                'message': 'Two-factor authentication enabled successfully'
            })

        elif action == 'disable':
            # Require password or MFA code to disable
            password = data.get('password')
            mfa_code = data.get('code')

            # Verify either password or MFA code
            verified = False

            if password and user.get('provider') == 'email':
                verified = verify_password(password, user.get('password_hash', ''))
            elif mfa_code and user.get('mfa_enabled'):
                totp = pyotp.TOTP(user.get('mfa_secret', ''))
                verified = totp.verify(mfa_code, valid_window=1)

            if not verified:
                return jsonify({
                    'success': False,
                    'error': 'Verification failed'
                }), 401

            # Disable MFA
            user_id = session['user_id']
            if USE_FIRESTORE:
                firestore_update_user(user_id, {
                    'mfa_enabled': False,
                    'mfa_secret': None
                })
            else:
                auth_storage['users'][user_id]['mfa_enabled'] = False
                auth_storage['users'][user_id]['mfa_secret'] = None
                save_auth_storage()

            # Clear MFA trusted flag
            session.pop('mfa_trusted', None)

            return jsonify({
                'success': True,
                'message': 'Two-factor authentication disabled'
            })

        else:
            return jsonify({
                'success': False,
                'error': 'Invalid action'
            }), 400

    except Exception as e:
        logger.error(f"Error toggling MFA: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to update MFA settings'
        }), 500

@app.route('/api/user/export-data', methods=['POST'])
@require_auth
@limiter.limit("3 per hour")
def export_user_data():
    """Export all user data as JSON"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404

        user_id = session['user_id']

        # Gather all user data
        export_data = {
            'profile': {
                'email': user['email'],
                'name': user['name'],
                'provider': user.get('provider'),
                'account_type': user.get('account_type'),
                'created_at': user.get('created_at'),
                'last_login': user.get('last_login')
            },
            'estates': [],
            'inventory': [],
            'documents': []
        }

        # Get user's estates
        if USE_FIRESTORE:
            estates = storage_service.get_user_estates(user_id)
            export_data['estates'] = estates

            # Get inventory and documents for each estate
            for estate in estates:
                estate_id = estate.get('id')
                inventory = storage_service.get_inventory(estate_id)
                documents = storage_service.get_documents(estate_id)
                export_data['inventory'].extend(inventory)
                export_data['documents'].extend(documents)
        else:
            # Fallback to JSON storage
            export_data['inventory'] = [
                item for item in inventory_storage.values()
                if item.get('user_id') == user_id
            ]

        # Create JSON file
        json_data = json.dumps(export_data, indent=2)

        return jsonify({
            'success': True,
            'data': json_data,
            'filename': f'myestateally_data_{user_id}_{datetime.now().strftime("%Y%m%d")}.json'
        })

    except Exception as e:
        logger.error(f"Error exporting user data: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to export data'
        }), 500

@app.route('/api/user/account', methods=['DELETE'])
@require_auth
@limiter.limit("2 per hour")
def delete_account():
    """Permanently delete user account and all associated data"""
    try:
        data = request.get_json()
        user = get_current_user()

        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404

        # Require password verification
        password = data.get('password')
        mfa_code = data.get('mfa_code')
        confirmation = data.get('confirmation', '')

        # Verify password (or MFA for OAuth users)
        verified = False
        if user.get('provider') == 'email':
            if not password:
                return jsonify({
                    'success': False,
                    'error': 'Password required'
                }), 400
            verified = verify_password(password, user.get('password_hash', ''))
        else:
            # OAuth users can delete with just confirmation
            verified = True

        if not verified:
            return jsonify({
                'success': False,
                'error': 'Password incorrect'
            }), 401

        # Require confirmation text
        if confirmation.upper() != 'DELETE MY ACCOUNT':
            return jsonify({
                'success': False,
                'error': 'Please type "DELETE MY ACCOUNT" to confirm'
            }), 400

        # Verify MFA if enabled
        if user.get('mfa_enabled') and mfa_code:
            import pyotp
            totp = pyotp.TOTP(user.get('mfa_secret', ''))
            if not totp.verify(mfa_code, valid_window=1):
                return jsonify({
                    'success': False,
                    'error': 'Invalid MFA code'
                }), 401

        user_id = session['user_id']

        # Delete all user data
        if USE_FIRESTORE:
            # Delete user estates and all associated data
            estates = storage_service.get_user_estates(user_id)
            for estate in estates:
                estate_id = estate.get('id')
                # Delete inventory
                storage_service.delete_collection(f'estates/{estate_id}/inventory')
                # Delete documents
                storage_service.delete_collection(f'estates/{estate_id}/documents')
                # Delete estate
                storage_service.delete_document('estates', estate_id)

            # Delete user document
            storage_service.delete_document('users', user_id)
        else:
            # Delete from JSON storage
            if user_id in auth_storage['users']:
                del auth_storage['users'][user_id]
                save_auth_storage()

            # Delete inventory items
            inventory_to_delete = [
                item_id for item_id, item in inventory_storage.items()
                if item.get('user_id') == user_id
            ]
            for item_id in inventory_to_delete:
                del inventory_storage[item_id]
            save_storage('inventory.json', inventory_storage)

        # Clear session
        session.clear()

        return jsonify({
            'success': True,
            'message': 'Account deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting account: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to delete account'
        }), 500

# ===== EMAIL NOTIFICATION SYSTEM =====

def initialize_email_templates():
    """Initialize email templates"""
    notification_storage['templates'] = {
        'family_invitation': {
            'subject': 'You\'re invited to view {owner_name}\'s MyEstateAlly inventory',
            'html_body': '''
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #8B5CF6, #A855F7); padding: 30px; text-align: center; color: white;">
                    <h1 style="margin: 0; font-size: 28px;">🏠 MyEstateAlly</h1>
                    <p style="margin: 10px 0 0 0; font-size: 16px;">AI-Powered Estate Management</p>
                </div>
                <div style="padding: 30px; background: #f9f9f9;">
                    <h2 style="color: #333; margin-top: 0;">You're Invited!</h2>
                    <p style="color: #666; font-size: 16px; line-height: 1.6;">
                        {owner_name} has invited you to view their estate inventory on MyEstateAlly. 
                        You can browse items, see what's available, and tag items you're interested in.
                    </p>
                    <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #8B5CF6;">
                        <p style="margin: 0; color: #333;"><strong>Your Member Code:</strong> {member_code}</p>
                        <p style="margin: 10px 0 0 0; color: #666; font-size: 14px;">Keep this code private - it's your unique access key</p>
                    </div>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{share_link}" style="background: #8B5CF6; color: white; padding: 15px 30px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                            View Inventory
                        </a>
                    </div>
                </div>
            </body>
            </html>
            ''',
            'text_body': '''You're invited to view {owner_name}'s MyEstateAlly inventory!

{owner_name} has invited you to browse their estate inventory.

Your Member Code: {member_code}
Access Link: {share_link}'''
        }
    }

def send_email_notification(notification_type, recipient_email, template_data):
    """Send email notification using templates"""
    try:
        if notification_type not in notification_storage['templates']:
            logger.error(f"Unknown notification type: {notification_type}")
            return False
        
        template = notification_storage['templates'][notification_type]
        
        # Format subject and body with template data
        subject = template['subject'].format(**template_data)
        html_body = template['html_body'].format(**template_data)
        text_body = template['text_body'].format(**template_data)
        
        # Create email message
        msg = Message(
            subject=subject,
            recipients=[recipient_email],
            html=html_body,
            body=text_body
        )
        
        # Send email
        try:
            # Check if email credentials are configured
            if not app.config['MAIL_USERNAME'] or not app.config['MAIL_PASSWORD']:
                logger.warning("Email credentials not configured. Email not sent.")
                logger.info(f"EMAIL SIMULATION: {notification_type} to {recipient_email}")
                logger.info(f"Subject: {subject}")
                logger.info(f"Share Link: {template_data.get('share_link', 'N/A')}")
                
                # Log as simulated send for development
                notification_storage['sent'].append({
                    'type': notification_type,
                    'recipient': recipient_email,
                    'subject': subject,
                    'sent_at': datetime.now().isoformat(),
                    'status': 'simulated',
                    'share_link': template_data.get('share_link', 'N/A'),
                    'member_code': template_data.get('member_code', 'N/A')
                })
                
                return True
            
            # Actually send the email
            mail.send(msg)
            logger.info(f"EMAIL SENT: {notification_type} to {recipient_email}")
            logger.info(f"Subject: {subject}")
            
            # Log successful send
            notification_storage['sent'].append({
                'type': notification_type,
                'recipient': recipient_email,
                'subject': subject,
                'sent_at': datetime.now().isoformat(),
                'status': 'sent'
            })
            
            return True
        except Exception as send_error:
            logger.error(f"Failed to send email via SMTP: {str(send_error)}")
            # Log failed send
            notification_storage['sent'].append({
                'type': notification_type,
                'recipient': recipient_email,
                'subject': subject,
                'sent_at': datetime.now().isoformat(),
                'status': 'failed',
                'error': str(send_error)
            })
            return False
        
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False

@app.route('/api/notifications/send-invitation', methods=['POST'])
@require_auth
@limiter.limit("5 per hour")
def send_invitation_email():
    """Send family invitation email"""
    try:
        data = request.get_json()
        email = data.get('email')
        member_code = data.get('member_code')
        owner_name = data.get('owner_name', 'Estate Owner')
        
        if not email or not member_code:
            return jsonify({
                'success': False,
                'error': 'Email and member code required'
            }), 400
        
        # Generate share link
        share_link = f"https://myestateally.com/family/view/{member_code}"
        
        template_data = {
            'owner_name': owner_name,
            'member_code': member_code,
            'share_link': share_link
        }
        
        success = send_email_notification('family_invitation', email, template_data)
        
        return jsonify({
            'success': success,
            'message': 'Invitation sent successfully' if success else 'Failed to send invitation'
        })
        
    except Exception as e:
        logger.error(f"Error sending invitation: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to send invitation'
        }), 500

@app.route('/api/estates', methods=['GET'])
@require_auth
def list_estates():
    """Get all estates for the current user"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        user_id = user.get('id') or session.get('user_id')
        estates = get_user_estates(user_id)
        
        return jsonify({
            'success': True,
            'estates': estates,
            'current_estate_id': get_current_estate_id()
        })
    except Exception as e:
        logger.error(f"Error listing estates: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to list estates'
        }), 500

@app.route('/api/estates', methods=['POST'])
@require_auth
def create_estate():
    """Create a new estate"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        data = request.get_json()
        estate_name = data.get('name', '').strip()
        
        if not estate_name:
            return jsonify({
                'success': False,
                'error': 'Estate name is required'
            }), 400
        
        user_id = user.get('id') or session.get('user_id')
        estate_id = str(uuid.uuid4())

        # Create estate data
        estate_data = {
            'id': estate_id,
            'name': estate_name,
            'owner_id': user_id,
            'created_at': datetime.now().isoformat(),
            'members': {}
        }

        # Save to Firestore
        if not storage_service.add_document('estates', estate_id, estate_data):
            return jsonify({'success': False, 'error': 'Failed to create estate'}), 500

        # Update user's estate list
        user_doc = firestore_get_user(user_id)
        if user_doc:
            estates = user_doc.get('estates', [])
            if estate_id not in estates:
                estates.append(estate_id)
                firestore_update_user(user_id, {'estates': estates})

        # Set as current estate (use both for compatibility)
        session['estate_id'] = estate_id
        session['current_estate_id'] = estate_id

        # Save as user's last used estate
        if user_id in auth_storage['users']:
            auth_storage['users'][user_id]['last_used_estate'] = estate_id
            save_auth_storage()

        return jsonify({
            'success': True,
            'message': 'Estate created successfully',
            'estate': {
                'id': estate_id,
                'name': estate_name,
                'owner_id': user_id,
                'user_role': 'owner'
            }
        })
    except Exception as e:
        logger.error(f"Error creating estate: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to create estate'
        }), 500

@app.route('/api/estates/current', methods=['GET'])
@require_auth
def get_current_estate():
    """Get current estate information"""
    try:
        estate_id = get_current_estate_id()
        if not estate_id:
            return jsonify({
                'success': True,
                'estate': None,
                'message': 'No estate selected'
            })
        
        # Get estate from Firestore
        estate = firestore_get_estate(estate_id)
        if not estate:
            # Clear invalid estate from session
            session.pop('estate_id', None)
            session.pop('current_estate_id', None)
            return jsonify({
                'success': True,
                'estate': None,
                'message': 'Estate not found'
            })

        # Add user's role
        user = get_current_user()
        user_id = user.get('id') if user else session.get('user_id')
        if estate.get('owner_id') == user_id:
            estate['user_role'] = 'owner'
        elif user_id in estate.get('members', {}):
            estate['user_role'] = estate['members'][user_id].get('role', 'member')
        
        return jsonify({
            'success': True,
            'estate': estate
        })
    except Exception as e:
        logger.error(f"Error getting current estate: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get current estate'
        }), 500

@app.route('/api/estates/switch', methods=['POST'])
@require_auth
def switch_estate():
    """Switch to a different estate"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        data = request.get_json()
        estate_id = data.get('estate_id')
        
        if not estate_id:
            return jsonify({
                'success': False,
                'error': 'Estate ID is required'
            }), 400
        
        user_id = user.get('id') or session.get('user_id')
        
        # Verify user has access to this estate
        if not user_has_estate_access(user_id, estate_id):
            return jsonify({
                'success': False,
                'error': 'Access denied to this estate'
            }), 403

        # Set as current estate (using current_estate_id for consistency)
        session['estate_id'] = estate_id
        session['current_estate_id'] = estate_id

        # Save as user's last used estate
        if user_id in auth_storage['users']:
            auth_storage['users'][user_id]['last_used_estate'] = estate_id
            save_auth_storage()

        estate = estate_storage['estates'][estate_id].copy()
        estate['id'] = estate_id

        return jsonify({
            'success': True,
            'message': 'Estate switched successfully',
            'estate': estate
        })
    except Exception as e:
        logger.error(f"Error switching estate: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to switch estate'
        }), 500

@app.route('/api/estates/<estate_id>/invite', methods=['POST'])
@require_auth
@limiter.limit("10 per hour")
def invite_to_estate(estate_id):
    """Invite a user to an estate"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        if estate_id not in estate_storage['estates']:
            return jsonify({
                'success': False,
                'error': 'Estate not found'
            }), 404
        
        user_id = user.get('id') or session.get('user_id')
        estate = estate_storage['estates'][estate_id]
        
        # Only owner can invite
        if estate.get('owner_id') != user_id:
            return jsonify({
                'success': False,
                'error': 'Only estate owner can invite members'
            }), 403
        
        data = request.get_json()
        invitee_email = data.get('email', '').strip().lower()
        role = data.get('role', 'member')  # 'member' or 'viewer'
        
        if not invitee_email:
            return jsonify({
                'success': False,
                'error': 'Email is required'
            }), 400
        
        # Find user by email
        invitee_user_id = None
        for uid, u in auth_storage['users'].items():
            if u.get('email', '').lower() == invitee_email:
                invitee_user_id = uid
                break
        
        if not invitee_user_id:
            return jsonify({
                'success': False,
                'error': 'User not found. They must sign up first.'
            }), 404
        
        # Add to estate members
        if 'members' not in estate:
            estate['members'] = {}
        estate['members'][invitee_user_id] = {
            'role': role,
            'joined_at': datetime.now().isoformat()
        }
        
        # Add to user's estate list
        if invitee_user_id not in estate_storage['user_estates']:
            estate_storage['user_estates'][invitee_user_id] = []
        if estate_id not in estate_storage['user_estates'][invitee_user_id]:
            estate_storage['user_estates'][invitee_user_id].append(estate_id)
        
        save_estate_storage()
        
        return jsonify({
            'success': True,
            'message': 'User invited to estate successfully'
        })
    except Exception as e:
        logger.error(f"Error inviting to estate: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to invite user'
        }), 500

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status"""
    try:
        if is_authenticated():
            user = get_current_user()
            user_id = user.get('id') or session.get('user_id')
            
            # Get user's estates
            estates = get_user_estates(user_id)
            current_estate_id = get_current_estate_id()
            current_estate = None

            if current_estate_id:
                current_estate = firestore_get_estate(current_estate_id)
                if current_estate:
                    current_estate['id'] = current_estate_id
            
            return jsonify({
                'success': True,
                'authenticated': True,
                'user': {
                    'id': user['id'],
                    'email': user['email'],
                    'name': user['name'],
                    'provider': user['provider'],
                    'created_at': user['created_at'],
                    'last_login': user['last_login']
                },
                'estates': estates,
                'current_estate': current_estate,
                'current_estate_id': current_estate_id
            })
        else:
            return jsonify({
                'success': True,
                'authenticated': False
            })
    except Exception as e:
        logger.error(f"Error checking auth status: {str(e)}")
        return jsonify({
            'success': False,
            'authenticated': False,
            'error': str(e)
        }), 500

# Initialize email templates on startup
initialize_email_templates()

# ===== PDF REPORT GENERATION SYSTEM =====

def generate_estate_valuation_report(user_id, report_type='full'):
    """Generate professional estate valuation PDF report"""
    try:
        # Get user inventory
        user_items = [item for item in inventory_storage.values() if item.get('user_id') == user_id]
        
        if not user_items:
            return None
        
        # Create PDF buffer
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor('#8B5CF6'),
            alignment=1  # Center
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            textColor=colors.HexColor('#4A5568')
        )
        
        # Build PDF content
        story = []
        
        # Title
        story.append(Paragraph("MyEstateAlly Estate Valuation Report", title_style))
        story.append(Spacer(1, 12))
        
        # Report metadata
        report_date = datetime.now().strftime("%B %d, %Y")
        story.append(Paragraph(f"<b>Report Date:</b> {report_date}", styles['Normal']))
        story.append(Paragraph(f"<b>Total Items:</b> {len(user_items)}", styles['Normal']))
        
        # Calculate totals
        total_value = sum(float(item.get('estimated_value', 0)) for item in user_items)
        for_sale_items = [item for item in user_items if item.get('for_sale', False)]
        
        story.append(Paragraph(f"<b>Total Estimated Value:</b> ${total_value:,.2f}", styles['Normal']))
        story.append(Paragraph(f"<b>Items For Sale:</b> {len(for_sale_items)}", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Category breakdown
        story.append(Paragraph("Category Breakdown", heading_style))
        
        categories = {}
        for item in user_items:
            category = item.get('category', 'Uncategorized')
            if category not in categories:
                categories[category] = {'count': 0, 'value': 0}
            categories[category]['count'] += 1
            categories[category]['value'] += float(item.get('estimated_value', 0))
        
        # Category table
        category_data = [['Category', 'Items', 'Total Value', 'Percentage']]
        for category, data in sorted(categories.items()):
            percentage = (data['value'] / total_value * 100) if total_value > 0 else 0
            category_data.append([
                category,
                str(data['count']),
                f"${data['value']:,.2f}",
                f"{percentage:.1f}%"
            ])
        
        category_table = Table(category_data)
        category_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8B5CF6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(category_table)
        story.append(Spacer(1, 20))
        
        # Detailed inventory
        if report_type == 'full':
            story.append(Paragraph("Detailed Inventory", heading_style))
            
            # Sort items by value (highest first)
            sorted_items = sorted(user_items, key=lambda x: float(x.get('estimated_value', 0)), reverse=True)
            
            inventory_data = [['Item Name', 'Category', 'Condition', 'Estimated Value', 'For Sale']]
            for item in sorted_items:
                inventory_data.append([
                    item.get('name', 'Unknown'),
                    item.get('category', 'Uncategorized'),
                    item.get('condition', 'Good'),
                    f"${float(item.get('estimated_value', 0)):,.2f}",
                    'Yes' if item.get('for_sale', False) else 'No'
                ])
            
            inventory_table = Table(inventory_data)
            inventory_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8B5CF6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8)
            ]))
            
            story.append(inventory_table)
        
        # Footer
        story.append(Spacer(1, 30))
        story.append(Paragraph("This report was generated by MyEstateAlly - AI-Powered Estate Management", styles['Normal']))
        story.append(Paragraph(f"Generated on {report_date} at {datetime.now().strftime('%I:%M %p')}", styles['Normal']))
        
        # Build PDF
        doc.build(story)
        
        # Get PDF data
        pdf_data = buffer.getvalue()
        buffer.close()
        
        return pdf_data
        
    except Exception as e:
        logger.error(f"Error generating PDF report: {str(e)}")
        return None

def generate_family_interest_report(estate_id: str):
    """Generate family interest analytics PDF report"""
    try:
        estate_data = get_family_estate_data(estate_id)
        wanted_items = estate_data.get('wanted_items', {})
        members = estate_data.get('members', {})

        if not wanted_items:
            return None
        
        # Create PDF buffer
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor('#8B5CF6'),
            alignment=1
        )
        
        # Build PDF content
        story = []
        
        # Title
        story.append(Paragraph("MyEstateAlly Family Interest Report", title_style))
        story.append(Spacer(1, 12))
        
        # Report metadata
        report_date = datetime.now().strftime("%B %d, %Y")
        story.append(Paragraph(f"<b>Report Date:</b> {report_date}", styles['Normal']))
        story.append(Paragraph(f"<b>Family Members:</b> {len(members)}", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Interest summary
        interest_data = [['Item', 'Interested Members', 'Conflict Level']]
        
        # Analyze wanted items
        item_interest = {}
        for member_code, wanted_list in wanted_items.items():
            member_name = members.get(member_code, {}).get('name', member_code)
            for wanted in wanted_list:
                item_id = wanted.get('item_id')
                if not item_id:
                    continue
                item_interest.setdefault(item_id, []).append(member_name)
        
        # Sort by conflict level (most wanted first)
        sorted_items = sorted(item_interest.items(), key=lambda x: len(x[1]), reverse=True)
        
        for item_id, interested_members in sorted_items:
            item = inventory_storage.get(item_id, {})
            if item.get('estate_id') != estate_id:
                continue
            item_name = item.get('name', 'Unknown Item')
            conflict_level = 'High' if len(interested_members) > 2 else 'Medium' if len(interested_members) > 1 else 'Low'
            
            interest_data.append([
                item_name,
                ', '.join(interested_members),
                conflict_level
            ])
        
        if len(interest_data) > 1:
            interest_table = Table(interest_data)
            interest_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8B5CF6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 10)
            ]))
            
            story.append(interest_table)
        else:
            story.append(Paragraph("No family interest data available yet.", styles['Normal']))
        
        # Build PDF
        doc.build(story)
        
        # Get PDF data
        pdf_data = buffer.getvalue()
        buffer.close()
        
        return pdf_data
        
    except Exception as e:
        logger.error(f"Error generating family interest report: {str(e)}")
        return None

def generate_assignment_report(estate_id: str):
    """Generate assignment report showing who gets what items"""
    try:
        # Get all assigned items for the estate
        assigned_items = [
            item for item in inventory_storage.values()
            if item.get('assignedTo') and item.get('estate_id') == estate_id
        ]

        if not assigned_items:
            return None

        # Get family members for this estate
        estate_data = get_family_estate_data(estate_id)
        members = estate_data.get('members', {})
        
        # Create PDF buffer
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1,  # Center alignment
            textColor=colors.darkblue
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            textColor=colors.darkblue
        )
        
        # Build PDF content
        story = []
        
        # Title
        story.append(Paragraph("Estate Assignment Report", title_style))
        story.append(Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Summary section
        story.append(Paragraph("Assignment Summary", heading_style))
        
        # Count assignments by member
        member_assignments = {}
        total_value = 0
        
        for item in assigned_items:
            assigned_to = item.get('assignedTo', '')
            if assigned_to:
                if assigned_to not in member_assignments:
                    member_assignments[assigned_to] = {
                        'items': [],
                        'total_value': 0,
                        'member_name': members.get(assigned_to, {}).get('name', assigned_to)
                    }
                member_assignments[assigned_to]['items'].append(item)
                member_assignments[assigned_to]['total_value'] += item.get('estimatedValue', 0)
                total_value += item.get('estimatedValue', 0)
        
        # Summary table
        summary_data = [['Family Member', 'Items Assigned', 'Total Value']]
        for member_code, data in member_assignments.items():
            summary_data.append([
                data['member_name'],
                str(len(data['items'])),
                f"${data['total_value']:,.2f}"
            ])
        
        summary_table = Table(summary_data)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 20))
        
        # Detailed assignments by member
        for member_code, data in member_assignments.items():
            story.append(Paragraph(f"Assignments for {data['member_name']}", heading_style))
            
            # Create detailed table for this member
            detail_data = [['Item Name', 'Category', 'Value', 'Assignment Date', 'Reason']]
            
            for item in data['items']:
                detail_data.append([
                    item.get('name', 'Unnamed Item'),
                    item.get('category', 'Uncategorized'),
                    f"${item.get('estimatedValue', 0):,.2f}",
                    item.get('assigned_at', 'Unknown')[:10] if item.get('assigned_at') else 'Unknown',
                    item.get('assignment_reason', 'No reason provided')[:50] + ('...' if len(item.get('assignment_reason', '')) > 50 else '')
                ])
            
            detail_table = Table(detail_data, colWidths=[2*inch, 1*inch, 1*inch, 1*inch, 2*inch])
            detail_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8)
            ]))
            
            story.append(detail_table)
            story.append(Spacer(1, 15))
        
        # Footer
        story.append(Spacer(1, 30))
        story.append(Paragraph(f"Total Estate Value Assigned: ${total_value:,.2f}", styles['Heading3']))
        story.append(Paragraph(f"Total Items Assigned: {len(assigned_items)}", styles['Normal']))
        story.append(Paragraph(f"Report generated by MyEstateAlly Estate Management System", styles['Normal']))
        
        # Build PDF
        doc.build(story)
        
        # Get PDF data
        pdf_data = buffer.getvalue()
        buffer.close()
        
        return pdf_data
        
    except Exception as e:
        logger.error(f"Error generating assignment report: {str(e)}")
        return None

# ===== PDF REPORT ENDPOINTS =====

@app.route('/api/reports/estate-valuation', methods=['GET'])
@require_auth
def generate_estate_report():
    """Generate and download estate valuation report"""
    try:
        user_id = request.args.get('user_id', 'demo-user')
        report_type = request.args.get('type', 'full')  # full or summary
        
        pdf_data = generate_estate_valuation_report(user_id, report_type)
        
        if not pdf_data:
            return jsonify({
                'success': False,
                'error': 'No inventory data available for report'
            }), 400
        
        # Save PDF temporarily
        filename = f"estate_valuation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        temp_dir = tempfile.gettempdir()
        filepath = os.path.join(temp_dir, filename)
        
        with open(filepath, 'wb') as f:
            f.write(pdf_data)
        
        return jsonify({
            'success': True,
            'download_url': f'/api/reports/download/{filename}',
            'filename': filename,
            'message': 'Estate valuation report generated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error generating estate report: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate estate report'
        }), 500

@app.route('/api/reports/family-interest', methods=['GET'])
@require_auth
def generate_family_report():
    """Generate and download family interest report"""
    try:
        estate_id = get_current_estate_id()
        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        pdf_data = generate_family_interest_report(estate_id)

        if not pdf_data:
            return jsonify({
                'success': False,
                'error': 'No family interest data available for report'
            }), 400

        # Save PDF temporarily
        filename = f"family_interest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        temp_dir = tempfile.gettempdir()
        filepath = os.path.join(temp_dir, filename)

        with open(filepath, 'wb') as f:
            f.write(pdf_data)

        return jsonify({
            'success': True,
            'download_url': f'/api/reports/download/{filename}',
            'filename': filename,
            'message': 'Family interest report generated successfully'
        })

    except Exception as e:
        logger.error(f"Error generating family report: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate family report'
        }), 500

@app.route('/api/reports/download/<filename>')
def download_report(filename):
    """Download generated PDF report"""
    try:
        # Security: Prevent path traversal attacks
        if '..' in filename or filename.startswith('/') or filename.startswith('\\'):
            logger.warning(f"Path traversal attempt blocked in report download: {filename}")
            abort(404)

        return send_from_directory('/tmp', filename, as_attachment=True)
    except Exception as e:
        logger.error(f"Error downloading report: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Report not found'
        }), 404

@app.route('/api/reports/assignments', methods=['GET'])
@require_auth
def generate_assignment_report_api():
    """Generate and download assignment report showing who gets what"""
    try:
        estate_id = get_current_estate_id()
        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        pdf_data = generate_assignment_report(estate_id)

        if not pdf_data:
            return jsonify({
                'success': False,
                'error': 'No assignment data available for report'
            }), 400

        # Save PDF temporarily
        filename = f"estate_assignments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        temp_dir = tempfile.gettempdir()
        filepath = os.path.join(temp_dir, filename)

        with open(filepath, 'wb') as f:
            f.write(pdf_data)

        return jsonify({
            'success': True,
            'download_url': f'/api/reports/download/{filename}',
            'filename': filename,
            'message': 'Assignment report generated successfully'
        })

    except Exception as e:
        logger.error(f"Error generating assignment report: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate assignment report'
        }), 500

# ============================================================================
# EXPORT ENDPOINTS (CSV, Excel, PDF Inventory Report)
# ============================================================================

@app.route('/api/export/inventory/csv', methods=['GET'])
@require_auth
def export_inventory_csv():
    """Export inventory to CSV format"""
    try:
        estate_id = get_current_estate_id()
        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        # Get inventory items
        items = firestore_list_inventory_items()
        if items is None:
            items = []

        # Filter by estate
        items = [item for item in items if item.get('estate_id') == estate_id]

        if not items:
            return jsonify({
                'success': False,
                'error': 'No inventory items to export'
            }), 400

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            'Item Name',
            'Category',
            'Description',
            'Estimated Value',
            'For Sale',
            'Sale Price',
            'Condition',
            'Location',
            'Assigned To',
            'Status',
            'Date Added'
        ])

        # Write data
        for item in items:
            writer.writerow([
                item.get('name', ''),
                item.get('category', ''),
                item.get('description', ''),
                f"${item.get('estimated_value', 0):.2f}",
                'Yes' if item.get('for_sale') else 'No',
                f"${item.get('sale_price', 0):.2f}" if item.get('for_sale') else '',
                item.get('condition', ''),
                item.get('location', ''),
                item.get('assigned_to', ''),
                item.get('status', 'active'),
                item.get('dateAdded', '')
            ])

        # Create response
        csv_data = output.getvalue()
        output.close()

        response = make_response(csv_data)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=inventory_{datetime.now().strftime("%Y%m%d")}.csv'

        return response

    except Exception as e:
        logger.error(f"Error exporting CSV: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to export inventory'
        }), 500

@app.route('/api/export/inventory/pdf', methods=['GET'])
@require_auth
def export_inventory_pdf():
    """Export complete inventory to a polished, branded PDF estate report."""
    try:
        estate_id = get_current_estate_id()
        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        items = firestore_list_inventory_items() or []
        items = [i for i in items if i.get('estate_id') == estate_id]

        if not items:
            return jsonify({'success': False, 'error': 'No inventory items to export'}), 400

        # Estate name
        user_id = session.get('user_id', '')
        estate_name = 'Estate'
        try:
            estates = storage_service.list_estates(user_id) or []
            for e in estates:
                if e.get('id') == estate_id:
                    estate_name = e.get('name', 'Estate')
                    break
        except Exception:
            pass

        user_name = session.get('user_email', 'Estate Owner')

        pdf_data = _build_inventory_pdf(items, estate_name, user_name)

        safe_name = ''.join(c if c.isalnum() else '_' for c in estate_name).lower()
        filename = f"{safe_name}_inventory_{datetime.now().strftime('%Y%m%d')}.pdf"

        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        logger.error(f"Error exporting PDF: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to generate PDF report'}), 500


def _build_inventory_pdf(items, estate_name, user_name):
    """
    Build a professional branded estate inventory PDF.
    Returns raw bytes of the PDF.
    """
    # ── Palette ──────────────────────────────────────────────────────────────
    NAVY      = colors.HexColor('#0a1628')
    NAVY_MID  = colors.HexColor('#142238')
    GOLD      = colors.HexColor('#c9a84c')
    GOLD_DARK = colors.HexColor('#a0832e')
    WHITE     = colors.white
    LIGHT_BG  = colors.HexColor('#f8f7f4')
    BORDER    = colors.HexColor('#e2d9c5')
    MUTED     = colors.HexColor('#6b7280')
    TEXT      = colors.HexColor('#1f2937')
    TEXT_SUB  = colors.HexColor('#374151')

    PAGE_W = letter[0]
    CONTENT_W = PAGE_W - 1.2 * inch   # left+right margin = 0.6" each
    PHOTO_W   = 1.35 * inch
    DETAIL_W  = CONTENT_W - PHOTO_W - 0.1 * inch

    # ── Styles ────────────────────────────────────────────────────────────────
    def ps(name, **kw):
        base = kw.pop('parent', None)
        s = ParagraphStyle(name, parent=base)
        for k, v in kw.items():
            setattr(s, k, v)
        return s

    cover_title  = ps('CoverTitle',  fontSize=26, fontName='Helvetica-Bold',
                       textColor=WHITE, alignment=1, leading=32, spaceAfter=4)
    cover_estate = ps('CoverEstate', fontSize=15, fontName='Helvetica-Bold',
                       textColor=GOLD,  alignment=1, leading=20, spaceAfter=2)
    cover_meta   = ps('CoverMeta',   fontSize=10, fontName='Helvetica',
                       textColor=colors.HexColor('#94a3b8'), alignment=1, leading=14)
    section_hdr  = ps('SectionHdr',  fontSize=14, fontName='Helvetica-Bold',
                       textColor=NAVY, spaceAfter=6, spaceBefore=4)
    cat_label    = ps('CatLabel',    fontSize=10, fontName='Helvetica-Bold',
                       textColor=WHITE)
    item_name    = ps('ItemName',    fontSize=11, fontName='Helvetica-Bold',
                       textColor=TEXT,  leading=14, spaceAfter=2)
    item_detail  = ps('ItemDetail',  fontSize=8,  fontName='Helvetica',
                       textColor=TEXT_SUB, leading=12)
    item_desc    = ps('ItemDesc',    fontSize=8,  fontName='Helvetica',
                       textColor=MUTED, leading=12, spaceAfter=0)
    footer_style = ps('Footer',      fontSize=7,  fontName='Helvetica',
                       textColor=MUTED, alignment=1)

    def stat_label(t): return Paragraph(t, ps(f'sl_{t}', fontSize=9, fontName='Helvetica-Bold', textColor=MUTED))
    def stat_value(t): return Paragraph(t, ps(f'sv_{t}', fontSize=14, fontName='Helvetica-Bold', textColor=NAVY, alignment=1))

    # ── Pre-process ───────────────────────────────────────────────────────────
    total_value = sum((i.get('estimatedValue') or i.get('estimated_value') or 0) for i in items)
    dest_map    = {'sell': 'For Sale', 'family': 'For Family', 'donate': 'Donate',
                   'charity': 'Charity', 'keep': 'Keep', 'discard': 'Discard'}

    categories = {}
    for item in items:
        cat = item.get('category') or 'Uncategorized'
        if cat not in categories:
            categories[cat] = {'count': 0, 'value': 0.0}
        categories[cat]['count'] += 1
        categories[cat]['value'] += (item.get('estimatedValue') or item.get('estimated_value') or 0)

    # ── Page-number callback ──────────────────────────────────────────────────
    def add_page_decorations(canvas, doc):
        canvas.saveState()
        # Bottom gold line + page number
        canvas.setFillColor(GOLD)
        canvas.rect(0.6 * inch, 0.38 * inch, CONTENT_W, 1.5, fill=1, stroke=0)
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(MUTED)
        canvas.drawCentredString(PAGE_W / 2, 0.25 * inch, f'Page {doc.page}  ·  MyEstateAlly Estate Inventory Report  ·  myestateally.com')
        canvas.restoreState()

    # ── Build story ───────────────────────────────────────────────────────────
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        leftMargin=0.6*inch, rightMargin=0.6*inch,
        topMargin=0.6*inch,  bottomMargin=0.65*inch
    )
    story = []

    # ── Cover block ───────────────────────────────────────────────────────────
    cover_rows = [
        [Paragraph('Estate Inventory Report', cover_title)],
        [Paragraph(estate_name, cover_estate)],
        [Spacer(1, 0.1*inch)],
        [Paragraph(f'Prepared for: {user_name}', cover_meta)],
        [Paragraph(f'Generated: {datetime.now().strftime("%B %d, %Y")}', cover_meta)],
        [Spacer(1, 0.25*inch)],
    ]
    cover_tbl = Table(cover_rows, colWidths=[CONTENT_W])
    cover_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), NAVY),
        ('TOPPADDING',    (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING',   (0, 0), (-1, -1), 24),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 24),
        ('TOPPADDING',    (0, 0), (0, 0),  28),
        ('BOTTOMPADDING', (0, -1), (0, -1), 24),
        ('LINEABOVE',     (0, 0), (-1, 0),  3, GOLD),
        ('LINEBELOW',     (0, -1), (-1, -1), 2, GOLD),
    ]))
    story.append(cover_tbl)
    story.append(Spacer(1, 0.3*inch))

    # ── Stats row ─────────────────────────────────────────────────────────────
    sell_ct   = sum(1 for i in items if i.get('destination') == 'sell')
    family_ct = sum(1 for i in items if i.get('destination') == 'family')
    donate_ct = sum(1 for i in items if i.get('destination') in ('donate','charity'))

    stats_data = [[
        [stat_label('TOTAL ITEMS'),   stat_value(str(len(items)))],
        [stat_label('EST. VALUE'),     stat_value(f'${total_value:,.0f}')],
        [stat_label('FOR SALE'),       stat_value(str(sell_ct))],
        [stat_label('FOR FAMILY'),     stat_value(str(family_ct))],
        [stat_label('DONATE/CHARITY'), stat_value(str(donate_ct))],
    ]]
    col_w = CONTENT_W / 5
    stats_tbl = Table(stats_data, colWidths=[col_w]*5)
    stats_tbl.setStyle(TableStyle([
        ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('BOX',           (0, 0), (-1, -1), 0.5, BORDER),
        ('INNERGRID',     (0, 0), (-1, -1), 0.5, BORDER),
        ('BACKGROUND',    (0, 0), (-1, -1), LIGHT_BG),
    ]))
    story.append(stats_tbl)
    story.append(Spacer(1, 0.3*inch))

    # ── Category summary table ────────────────────────────────────────────────
    story.append(Paragraph('Breakdown by Category', section_hdr))
    cat_rows = [['Category', 'Items', 'Est. Value']]
    for cat_n, cat_d in sorted(categories.items()):
        cat_rows.append([cat_n, str(cat_d['count']), f"${cat_d['value']:,.2f}"])
    cat_tbl = Table(cat_rows, colWidths=[CONTENT_W - 2*inch, 0.8*inch, 1.2*inch])
    cat_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  NAVY),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  WHITE),
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 9),
        ('ALIGN',         (1, 0), (-1, -1), 'RIGHT'),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [WHITE, LIGHT_BG]),
        ('BOX',           (0, 0), (-1, -1), 0.5, BORDER),
        ('INNERGRID',     (0, 0), (-1, -1), 0.5, BORDER),
    ]))
    story.append(cat_tbl)
    story.append(PageBreak())

    # ── Full item listing ─────────────────────────────────────────────────────
    story.append(Paragraph('Full Inventory', section_hdr))

    items_by_cat = {}
    for item in items:
        cat = item.get('category') or 'Uncategorized'
        items_by_cat.setdefault(cat, []).append(item)

    for cat_n in sorted(items_by_cat.keys()):
        # Category header bar
        cat_bar = Table([[Paragraph(f'  {cat_n.upper()}', cat_label)]], colWidths=[CONTENT_W])
        cat_bar.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), GOLD),
            ('TOPPADDING',    (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LINEABOVE',     (0, 0), (-1, 0),  1, GOLD_DARK),
        ]))
        story.append(KeepTogether([cat_bar, Spacer(1, 2)]))

        for item in items_by_cat[cat_n]:
            # Photo cell
            photo_cell = Spacer(PHOTO_W, PHOTO_W)
            photo_b64 = item.get('photo_data', '')
            if photo_b64:
                try:
                    raw = base64.b64decode(photo_b64)
                    img_buf = BytesIO(raw)
                    photo_cell = RLImage(img_buf, width=PHOTO_W, height=PHOTO_W, kind='proportional')
                except Exception:
                    photo_cell = Paragraph('<font color="#9ca3af">[photo]</font>', item_detail)

            # Value & destination
            val  = item.get('estimatedValue') or item.get('estimated_value') or 0
            dest = dest_map.get(item.get('destination') or 'keep', 'Keep')

            # Detail paragraphs
            name_p = Paragraph(item.get('name') or 'Unnamed Item', item_name)

            meta_parts = []
            if item.get('condition'):  meta_parts.append(f"Condition: <b>{item['condition']}</b>")
            if item.get('location'):   meta_parts.append(f"Location: <b>{item['location']}</b>")
            meta_parts.append(f"Est. Value: <b>${val:,.2f}</b>")
            meta_parts.append(f"Status: <b>{dest}</b>")
            meta_p = Paragraph('  ·  '.join(meta_parts), item_detail)

            detail_cells = [name_p, meta_p]

            desc = (item.get('description') or '').strip()
            if desc:
                if len(desc) > 220:
                    desc = desc[:220] + '…'
                detail_cells.append(Paragraph(desc, item_desc))

            notes = (item.get('notes') or '').strip()
            if notes:
                detail_cells.append(Paragraph(f'<i>Notes: {notes[:160]}</i>', item_desc))

            row_tbl = Table(
                [[photo_cell, detail_cells]],
                colWidths=[PHOTO_W + 0.05*inch, DETAIL_W]
            )
            row_tbl.setStyle(TableStyle([
                ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING',    (0, 0), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
                ('LEFTPADDING',   (0, 0), (0,  -1), 4),
                ('LEFTPADDING',   (1, 0), (1,  -1), 10),
                ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
                ('LINEBELOW',     (0, 0), (-1, -1), 0.4, BORDER),
            ]))
            story.append(row_tbl)

        story.append(Spacer(1, 0.15*inch))

    # ── Footer note ───────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(
        'This report was generated by MyEstateAlly (myestateally.com). '
        'Estimated values are AI-assisted suggestions and are not certified appraisals. '
        'Consult a professional appraiser for items of significant value.',
        footer_style
    ))

    doc.build(story, onFirstPage=add_page_decorations, onLaterPages=add_page_decorations)
    return buffer.getvalue()

@app.route('/api/export/documents/csv', methods=['GET'])
@require_auth
def export_documents_csv():
    """Export documents list to CSV format"""
    try:
        estate_id = get_current_estate_id()
        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        # Get documents
        documents = storage_service.list_documents('documents')
        documents = [doc for doc in documents if doc.get('estate_id') == estate_id]

        if not documents:
            return jsonify({
                'success': False,
                'error': 'No documents to export'
            }), 400

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            'Filename',
            'Category',
            'Description',
            'File Size',
            'Upload Date'
        ])

        # Write data
        for doc in documents:
            file_size_mb = doc.get('file_size', 0) / (1024 * 1024)
            writer.writerow([
                doc.get('filename', ''),
                doc.get('category', ''),
                doc.get('description', ''),
                f"{file_size_mb:.2f} MB",
                doc.get('uploaded_at', '')
            ])

        csv_data = output.getvalue()
        output.close()

        response = make_response(csv_data)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=documents_{datetime.now().strftime("%Y%m%d")}.csv'

        return response

    except Exception as e:
        logger.error(f"Error exporting documents CSV: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to export documents'
        }), 500

@app.route('/api/items/<item_id>/dispose', methods=['POST'])
@require_auth
def dispose_item(item_id):
    """Mark an item as disposed (sold, donated, discarded)"""
    try:
        estate_id = get_current_estate_id()
        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        data = request.get_json()
        disposal_type = data.get('disposal_type')  # 'sold', 'donated', 'discarded'
        disposal_value = data.get('disposal_value', 0)
        disposal_notes = data.get('disposal_notes', '')
        disposal_date = data.get('disposal_date', datetime.now().isoformat())
        
        if not disposal_type:
            return jsonify({
                'success': False,
                'error': 'Disposal type required'
            }), 400
        
        if item_id not in inventory_storage or inventory_storage[item_id].get('estate_id') != estate_id:
            return jsonify({
                'success': False,
                'error': 'Item not found'
            }), 404
        
        # Update item with disposal information
        inventory_storage[item_id]['status'] = 'disposed'
        inventory_storage[item_id]['disposal_type'] = disposal_type
        inventory_storage[item_id]['disposal_value'] = float(disposal_value)
        inventory_storage[item_id]['disposal_notes'] = disposal_notes
        inventory_storage[item_id]['disposal_date'] = disposal_date
        inventory_storage[item_id]['lastModified'] = datetime.now().isoformat()
        
        # Try to save to Firestore
        try:
            firestore_update_inventory_item(inventory_storage[item_id])
        except:
            # Fall back to JSON storage
            save_storage('inventory.json', inventory_storage)
        
        return jsonify({
            'success': True,
            'message': f'Item marked as {disposal_type}',
            'item': inventory_storage[item_id]
        })
        
    except Exception as e:
        logger.error(f"Error disposing item: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to dispose item'
        }), 500

@app.route('/api/activity-log', methods=['GET'])
@require_auth
def get_activity_log_endpoint():
    """Get activity log for current estate"""
    try:
        estate_id = get_current_estate_id()
        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        limit = request.args.get('limit', 50, type=int)
        activities = get_activity_log(estate_id, limit)

        return jsonify({
            'success': True,
            'activities': activities
        })

    except Exception as e:
        logger.error(f"Error getting activity log: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get activity log'
        }), 500

@app.route('/api/items/<item_id>/claim', methods=['POST'])
@require_auth
def claim_item(item_id):
    """Claim an item (heir marks it as wanted)"""
    try:
        user_id = session.get('user_id')
        user_email = session.get('user_email')
        estate_id = get_current_estate_id()

        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        # Check permission - heirs and above can claim
        if not check_permission(user_id, estate_id, 'mark_wants'):
            return jsonify({
                'success': False,
                'error': 'You do not have permission to claim items'
            }), 403

        # Get item
        if item_id not in inventory_storage:
            fresh_storage = load_storage('inventory.json')
            if item_id not in fresh_storage:
                return jsonify({'success': False, 'error': 'Item not found'}), 404
            inventory_storage[item_id] = fresh_storage[item_id]

        item = inventory_storage[item_id]

        # Initialize claims array if not exists
        if 'claims' not in item:
            item['claims'] = []

        # Check if already claimed by this user
        if user_email in item['claims']:
            return jsonify({
                'success': False,
                'error': 'You have already claimed this item'
            }), 400

        # Add claim
        item['claims'].append(user_email)
        item['lastModified'] = datetime.now().isoformat()

        # Save to storage
        try:
            firestore_update_inventory_item(item)
        except:
            inventory_storage[item_id] = item
            save_storage('inventory.json', inventory_storage)

        # Log activity
        log_activity(
            estate_id=estate_id,
            user_email=user_email,
            action='claimed',
            item_id=item_id,
            item_name=item.get('name'),
            details={'total_claims': len(item['claims'])}
        )

        return jsonify({
            'success': True,
            'message': 'Item claimed successfully',
            'item': item,
            'has_conflict': len(item['claims']) > 1
        })

    except Exception as e:
        logger.error(f"Error claiming item: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to claim item'
        }), 500

@app.route('/api/items/<item_id>/unclaim', methods=['POST'])
@require_auth
def unclaim_item(item_id):
    """Unclaim an item (remove claim)"""
    try:
        user_id = session.get('user_id')
        user_email = session.get('user_email')
        estate_id = get_current_estate_id()

        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        # Check permission
        if not check_permission(user_id, estate_id, 'mark_wants'):
            return jsonify({
                'success': False,
                'error': 'You do not have permission to unclaim items'
            }), 403

        # Get item
        if item_id not in inventory_storage:
            fresh_storage = load_storage('inventory.json')
            if item_id not in fresh_storage:
                return jsonify({'success': False, 'error': 'Item not found'}), 404
            inventory_storage[item_id] = fresh_storage[item_id]

        item = inventory_storage[item_id]

        # Remove claim
        if 'claims' in item and user_email in item['claims']:
            item['claims'].remove(user_email)
            item['lastModified'] = datetime.now().isoformat()

            # Save to storage
            try:
                firestore_update_inventory_item(item)
            except:
                inventory_storage[item_id] = item
                save_storage('inventory.json', inventory_storage)

            # Log activity
            log_activity(
                estate_id=estate_id,
                user_email=user_email,
                action='unclaimed',
                item_id=item_id,
                item_name=item.get('name')
            )

            return jsonify({
                'success': True,
                'message': 'Claim removed successfully',
                'item': item
            })
        else:
            return jsonify({
                'success': False,
                'error': 'You have not claimed this item'
            }), 400

    except Exception as e:
        logger.error(f"Error unclaiming item: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to unclaim item'
        }), 500

@app.route('/api/ai/value-item', methods=['POST'])
@require_auth
@limiter.limit("30 per hour")
def ai_value_item():
    """Use AI to estimate item value from photo and description"""
    try:
        if not openai_client:
            return jsonify({
                'success': False,
                'error': 'AI features are not available. Please configure OPENAI_API_KEY.'
            }), 503

        data = request.get_json()
        item_name = data.get('name', '')
        item_description = data.get('description', '')
        item_category = data.get('category', '')
        photo_base64 = data.get('photo', '')

        if not item_name:
            return jsonify({
                'success': False,
                'error': 'Item name is required'
            }), 400

        # Build prompt for AI
        prompt = f"""Estimate the current market value of this item in USD.

Item Name: {item_name}
Category: {item_category}
Description: {item_description}

Provide:
1. Estimated value range (min-max)
2. Most likely value
3. Brief explanation of valuation
4. Condition assumptions

Format response as JSON:
{{
    "min_value": number,
    "max_value": number,
    "estimated_value": number,
    "explanation": "string",
    "condition": "string"
}}"""

        # Call OpenAI API
        messages = [
            {
                "role": "system",
                "content": "You are an expert appraiser specializing in household items, antiques, and personal property. Provide accurate market value estimates based on current market conditions."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        # Add image if provided
        if photo_base64 and photo_base64.startswith('data:image'):
            messages[1]["content"] = [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": photo_base64}
                }
            ]

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=500
        )

        ai_response = json.loads(response.choices[0].message.content)

        return jsonify({
            'success': True,
            'valuation': ai_response
        })

    except Exception as e:
        logger.error(f"Error with AI valuation: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get AI valuation'
        }), 500

@app.route('/api/ai/suggest-category', methods=['POST'])
@require_auth
def ai_suggest_category():
    """Use AI to suggest item category"""
    try:
        if not openai_client:
            return jsonify({
                'success': False,
                'error': 'AI features are not available'
            }), 503

        data = request.get_json()
        item_name = data.get('name', '')
        item_description = data.get('description', '')

        if not item_name:
            return jsonify({
                'success': False,
                'error': 'Item name is required'
            }), 400

        # Standard categories
        categories = [
            "Furniture", "Jewelry", "Electronics", "Artwork", "Collectibles",
            "Kitchenware", "Books", "Clothing", "Tools", "Appliances",
            "Antiques", "Vehicles", "Real Estate", "Musical Instruments", "Other"
        ]

        prompt = f"""Given this item, suggest the most appropriate category from this list: {', '.join(categories)}

Item Name: {item_name}
Description: {item_description}

Respond with JSON:
{{
    "category": "suggested category from the list",
    "confidence": "high/medium/low",
    "reason": "brief explanation"
}}"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that categorizes household items accurately."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=200
        )

        ai_response = json.loads(response.choices[0].message.content)

        return jsonify({
            'success': True,
            'suggestion': ai_response
        })

    except Exception as e:
        logger.error(f"Error with AI category suggestion: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get category suggestion'
        }), 500

@app.route('/api/ai/search', methods=['POST'])
@require_auth
@limiter.limit("30 per hour")
def ai_natural_language_search():
    """Natural language search for inventory items"""
    try:
        if not openai_client:
            return jsonify({
                'success': False,
                'error': 'AI features are not available'
            }), 503

        user_id = session.get('user_id')
        estate_id = get_current_estate_id()

        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        data = request.get_json()
        query = data.get('query', '')

        if not query:
            return jsonify({
                'success': False,
                'error': 'Search query is required'
            }), 400

        # Get all inventory items
        items = firestore_list_inventory_items() or []
        estate_items = [item for item in items if item.get('estate_id') == estate_id]

        # Create simplified item list for AI
        items_summary = [
            {
                'id': item.get('id'),
                'name': item.get('name'),
                'category': item.get('category'),
                'description': item.get('description', '')[:100],
                'value': item.get('estimatedValue', 0)
            }
            for item in estate_items
        ]

        prompt = f"""Given this natural language query: "{query}"

Find matching items from this inventory:
{json.dumps(items_summary, indent=2)}

Return item IDs that match the query. Consider name, category, description, and value.

Respond with JSON:
{{
    "matching_ids": ["id1", "id2", ...],
    "explanation": "why these items match"
}}"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a search assistant helping users find items in their estate inventory."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=1000
        )

        ai_response = json.loads(response.choices[0].message.content)
        matching_ids = ai_response.get('matching_ids', [])

        # Get full item details
        matching_items = [item for item in estate_items if item.get('id') in matching_ids]

        return jsonify({
            'success': True,
            'items': matching_items,
            'explanation': ai_response.get('explanation', '')
        })

    except Exception as e:
        logger.error(f"Error with AI search: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to perform AI search'
        }), 500

@app.route('/api/ai/lookup-item', methods=['POST'])
@require_auth
@limiter.limit("30 per hour")
def ai_lookup_item():
    """Use Gemini 2.0 Flash to identify, categorize, and value a new item. Supports vision via photos."""
    try:
        if not gemini_api_key:
            return jsonify({'success': False, 'error': 'AI features not available. Please configure GEMINI_API_KEY.'}), 503

        data = request.get_json()
        item_name = data.get('name', '').strip()
        item_description = data.get('description', '').strip()
        photos = data.get('photos', [])
        if not isinstance(photos, list):
            photos = []
        raw_photos = [p for p in photos[:4] if isinstance(p, str) and p.startswith('data:image')]
        photos = [p for p in raw_photos if len(p) <= 300000]
        oversized_count = len(raw_photos) - len(photos)
        if oversized_count:
            logger.warning(f"AI lookup: dropped {oversized_count} oversized photo(s) (each was >{len(raw_photos[0])//1000}KB)")

        if not item_name and not photos:
            if oversized_count:
                return jsonify({'success': False,
                                'error': 'Photo could not be sent to AI — it is still too large after compression. '
                                         'Please enter a name or description to help identify the item.'}), 400
            return jsonify({'success': False, 'error': 'Item name or at least one photo is required'}), 400

        categories = [
            "Furniture", "Jewelry", "Art", "Electronics", "Collectibles",
            "Clothing", "Books", "Kitchen", "Tools", "Other"
        ]

        name_clause = f"Item Name: {item_name}" if item_name else "Item Name: (identify from the photos)"
        desc_clause = f"Additional context: {item_description}" if item_description else ""
        photo_instruction = f"Examine the {len(photos)} provided photo(s) carefully to identify the item." if photos else ""

        prompt = f"""You are an expert estate appraiser helping catalog personal property for estate management.

{name_clause}
{desc_clause}
{photo_instruction}

Categories to choose from: {', '.join(categories)}

Respond with JSON only (no markdown, no code fences):
{{
    "item_name": "the identified item name (refine or confirm the provided name, or identify from photos)",
    "category": "one category from the list above",
    "description": "a concise 1-2 sentence description of the item and its notable characteristics",
    "estimated_value": 0,
    "value_min": 0,
    "value_max": 0,
    "confidence": "high/medium/low",
    "notes": "brief note on valuation basis or caveats"
}}

Replace the 0 placeholders with actual numeric USD estimates based on current resale market."""

        # Build Gemini REST API request — no SDK needed, uses requests library
        parts = [{"text": prompt}]
        for photo_data_url in photos:
            try:
                header, b64data = photo_data_url.split(',', 1)
                mime_type = header.split(':')[1].split(';')[0]  # e.g. image/jpeg
                parts.append({"inline_data": {"mime_type": mime_type, "data": b64data}})
            except Exception as img_err:
                logger.warning(f"Skipping malformed photo in AI lookup: {img_err}")

        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_api_key}"
        gemini_payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "maxOutputTokens": 512,
                "temperature": 0.2
            }
        }

        import requests as req_lib
        resp = req_lib.post(gemini_url, json=gemini_payload, timeout=30)
        resp.raise_for_status()
        gemini_data = resp.json()

        candidates = gemini_data.get('candidates', [])
        if not candidates:
            logger.error(f"Gemini returned no candidates: {gemini_data}")
            return jsonify({'success': False, 'error': 'AI returned no result. Try adding a name or description.'}), 503

        parts = candidates[0].get('content', {}).get('parts', [])
        if not parts:
            return jsonify({'success': False, 'error': 'AI returned empty response. Please try again.'}), 503

        raw_text = parts[0].get('text', '').strip()

        # Strip markdown fences Gemini sometimes wraps around JSON, even with responseMimeType set
        # Handle various formats: ```json...```, ```...```, or raw JSON
        original_text = raw_text
        if raw_text.startswith('```'):
            # Remove opening backticks and optional 'json' language tag
            lines = raw_text.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]  # Skip the opening ``` line
            # Remove closing backticks from the end
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            raw_text = '\n'.join(lines).strip()

        # If we still can't parse, log the raw response for debugging
        logger.info(f"AI Lookup raw response (first 200 chars): {original_text[:200]}")

        try:
            ai_response = json.loads(raw_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            logger.error(f"Raw text: {raw_text[:500]}")
            # Try to find JSON object in the text as a fallback
            import re
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if json_match:
                try:
                    ai_response = json.loads(json_match.group())
                    logger.info("Recovered JSON from regex match")
                except json.JSONDecodeError:
                    raise
            else:
                raise
        return jsonify({'success': True, 'lookup': ai_response})

    except req_lib.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'AI lookup timed out. Try with fewer photos.'}), 504
    except req_lib.exceptions.RequestException as e:
        logger.error(f"Gemini API request failed: {e}")
        return jsonify({'success': False, 'error': 'AI service unavailable. Please try again shortly.'}), 503
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error(f"Failed to parse Gemini response: {e}")
        return jsonify({'success': False, 'error': 'AI returned an unexpected format. Please try again.'}), 500
    except Exception as e:
        logger.error(f"Error with AI item lookup: {e}")
        return jsonify({'success': False, 'error': 'AI lookup failed. Please try again.'}), 500

@app.route('/api/ai/generate-listing', methods=['POST'])
@require_auth
@limiter.limit("30 per hour")
def ai_generate_listing():
    """Use Gemini to write marketplace-ready listing copy (title, description, price)
    for an inventory item — for posting on Facebook Marketplace, eBay, or Craigslist."""
    try:
        if not gemini_api_key:
            return jsonify({'success': False, 'error': 'AI features not available. Please configure GEMINI_API_KEY.'}), 503

        data = request.get_json()
        item_id = data.get('item_id', '')
        if not item_id:
            return jsonify({'success': False, 'error': 'item_id is required'}), 400

        item = firestore_get_inventory_item(item_id)
        if not item or item.get('estate_id') != get_current_estate_id():
            return jsonify({'success': False, 'error': 'Item not found'}), 404

        est_value = item.get('estimatedValue') or 0
        value_clause = f"The owner's estimated value is ${est_value:,.0f}." if est_value else ""

        prompt = f"""You are an expert at writing online marketplace listings that sell quickly
(Facebook Marketplace, eBay, Craigslist, Poshmark). For clothing, shoes, or accessories,
include brand, size, and material details in the description when visible — buyers on
Poshmark search by those.

Item name: {item.get('name', 'Unknown item')}
Category: {item.get('category', 'Other')}
Condition notes / description: {item.get('description', 'None provided')}
{value_clause}
Examine the photo if one is provided.

Write listing copy for this item. Respond with JSON only (no markdown, no code fences):
{{
    "title": "catchy, search-friendly listing title, max 75 characters, no ALL CAPS, no emoji",
    "description": "3-5 short paragraphs: what it is, condition, why it's great, pickup/shipping note placeholder. Friendly and honest tone. Plain text, no markdown.",
    "price": 0,
    "keywords": "5-8 comma-separated search keywords buyers would type"
}}

Replace the 0 with a realistic asking price in whole USD based on the resale market
(slightly above expected sale price to leave room for negotiation)."""

        parts = [{"text": prompt}]
        photo_b64 = item.get('photo_data', '')
        if photo_b64 and len(photo_b64) <= 300000:
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": photo_b64}})

        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_api_key}"
        gemini_payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "maxOutputTokens": 1024,
                "temperature": 0.6
            }
        }

        import requests as req_lib
        resp = req_lib.post(gemini_url, json=gemini_payload, timeout=30)
        resp.raise_for_status()
        gemini_data = resp.json()

        candidates = gemini_data.get('candidates', [])
        if not candidates:
            logger.error(f"Gemini returned no candidates for listing: {gemini_data}")
            return jsonify({'success': False, 'error': 'AI returned no result. Please try again.'}), 503

        resp_parts = candidates[0].get('content', {}).get('parts', [])
        if not resp_parts:
            return jsonify({'success': False, 'error': 'AI returned empty response. Please try again.'}), 503

        raw_text = resp_parts[0].get('text', '').strip()
        if raw_text.startswith('```'):
            raw_text = raw_text.split('```')[1]
            if raw_text.startswith('json'):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()

        listing = json.loads(raw_text)
        return jsonify({'success': True, 'listing': listing})

    except req_lib.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'AI request timed out. Please try again.'}), 504
    except req_lib.exceptions.RequestException as e:
        logger.error(f"Gemini API request failed for listing: {e}")
        return jsonify({'success': False, 'error': 'AI service unavailable. Please try again shortly.'}), 503
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error(f"Failed to parse Gemini listing response: {e}")
        return jsonify({'success': False, 'error': 'AI returned an unexpected format. Please try again.'}), 500
    except Exception as e:
        logger.error(f"Error generating listing: {e}")
        return jsonify({'success': False, 'error': 'Failed to generate listing. Please try again.'}), 500

@app.route('/api/estate/timeline', methods=['GET', 'POST'])
@require_auth
def estate_timeline():
    """Get or update estate settlement timeline"""
    try:
        estate_id = get_current_estate_id()
        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        estate_data = get_family_estate_data(estate_id)
        timeline = estate_data.setdefault('estate_timeline', [])

        if request.method == 'GET':
            return jsonify({
                'success': True,
                'timeline': timeline
            })

        # POST - add new task
        data = request.get_json()
        task = data.get('task')
        due_date = data.get('due_date')
        priority = data.get('priority', 'medium')
        status = data.get('status', 'pending')

        if not task:
            return jsonify({
                'success': False,
                'error': 'Task description required'
            }), 400

        task_id = str(uuid.uuid4())
        new_task = {
            'id': task_id,
            'task': task,
            'due_date': due_date,
            'priority': priority,
            'status': status,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }

        timeline.append(new_task)
        # Save changes to Firestore
        firestore_update_family_data(estate_id, {'estate_timeline': timeline})

        return jsonify({
            'success': True,
            'message': 'Task added to timeline',
            'task': new_task
        })

    except Exception as e:
        logger.error(f"Error managing estate timeline: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to manage estate timeline'
        }), 500

@app.route('/api/estate/timeline/<task_id>', methods=['PUT', 'DELETE'])
@require_auth
def update_timeline_task(task_id):
    """Update or delete a timeline task"""
    try:
        estate_id = get_current_estate_id()
        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        estate_data = get_family_estate_data(estate_id)
        timeline = estate_data.setdefault('estate_timeline', [])

        task_index = next((i for i, task in enumerate(timeline) if task.get('id') == task_id), None)

        if task_index is None:
            return jsonify({
                'success': False,
                'error': 'Task not found'
            }), 404

        if request.method == 'PUT':
            data = request.get_json()
            timeline[task_index].update({
                'task': data.get('task', timeline[task_index]['task']),
                'due_date': data.get('due_date', timeline[task_index].get('due_date')),
                'priority': data.get('priority', timeline[task_index]['priority']),
                'status': data.get('status', timeline[task_index]['status']),
                'updated_at': datetime.now().isoformat()
            })
            # Save changes to Firestore
            firestore_update_family_data(estate_id, {'estate_timeline': timeline})

            return jsonify({
                'success': True,
                'message': 'Task updated',
                'task': timeline[task_index]
            })
        else:
            deleted_task = timeline.pop(task_index)
            # Save changes to Firestore
            firestore_update_family_data(estate_id, {'estate_timeline': timeline})
            return jsonify({
                'success': True,
                'message': 'Task deleted',
                'task': deleted_task
            })

    except Exception as e:
        logger.error(f"Error managing timeline task: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to manage timeline task'
        }), 500

@app.route('/api/estate/disposal-summary', methods=['GET'])
@require_auth
def get_disposal_summary():
    """Get summary of disposed items for tax/estate purposes"""
    try:
        estate_id = get_current_estate_id()
        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        # Get all inventory items from Firestore
        all_items = firestore_list_inventory_items()
        disposed_items = [
            item for item in all_items
            if item.get('status') == 'disposed' and item.get('estate_id') == estate_id
        ]

        summary = {
            'total_disposed': len(disposed_items),
            'by_type': {},
            'total_value': 0,
            'tax_deductible': 0,
            'items': []
        }

        for item in disposed_items:
            disposal_type = item.get('disposal_type', 'unknown')
            disposal_value = float(item.get('disposal_value', 0))

            if disposal_type not in summary['by_type']:
                summary['by_type'][disposal_type] = {'count': 0, 'value': 0}

            summary['by_type'][disposal_type]['count'] += 1
            summary['by_type'][disposal_type]['value'] += disposal_value
            summary['total_value'] += disposal_value

            # Tax deductible items (donations)
            if disposal_type == 'donated':
                summary['tax_deductible'] += disposal_value

            summary['items'].append({
                'name': item.get('name', 'Unnamed'),
                'category': item.get('category', 'Uncategorized'),
                'disposal_type': disposal_type,
                'disposal_value': disposal_value,
                'disposal_date': item.get('disposal_date', ''),
                'disposal_notes': item.get('disposal_notes', '')
            })

        return jsonify({
            'success': True,
            'summary': summary
        })

    except Exception as e:
        logger.error(f"Error getting disposal summary: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get disposal summary'
        }), 500

# ===== ADVANCED SEARCH & FILTERING SYSTEM =====

def apply_inventory_filters(items, filters):
    """Apply advanced filters to inventory items"""
    try:
        filtered_items = items.copy()
        
        # Text search
        if filters.get('search'):
            search_term = filters['search'].lower()
            filtered_items = [
                item for item in filtered_items
                if search_term in item.get('name', '').lower() or
                   search_term in item.get('description', '').lower() or
                   search_term in item.get('category', '').lower()
            ]
        
        # Category filter
        if filters.get('category') and filters['category'] != 'all':
            filtered_items = [
                item for item in filtered_items
                if item.get('category', '').lower() == filters['category'].lower()
            ]
        
        # Room filter
        if filters.get('room') and filters['room'] != 'all':
            filtered_items = [
                item for item in filtered_items
                if item.get('room', '').lower() == filters['room'].lower()
            ]
        
        # Value range filter
        if filters.get('min_value') is not None:
            min_val = float(filters['min_value'])
            filtered_items = [
                item for item in filtered_items
                if float(item.get('estimated_value', 0)) >= min_val
            ]
        
        if filters.get('max_value') is not None:
            max_val = float(filters['max_value'])
            filtered_items = [
                item for item in filtered_items
                if float(item.get('estimated_value', 0)) <= max_val
            ]
        
        # Condition filter
        if filters.get('condition') and filters['condition'] != 'all':
            filtered_items = [
                item for item in filtered_items
                if item.get('condition', '').lower() == filters['condition'].lower()
            ]
        
        # For sale filter
        if filters.get('for_sale') is not None:
            for_sale = filters['for_sale'] in ['true', True, 1, '1']
            filtered_items = [
                item for item in filtered_items
                if item.get('for_sale', False) == for_sale
            ]
        
        # Date range filter
        if filters.get('date_from'):
            date_from = datetime.fromisoformat(filters['date_from'].replace('Z', '+00:00'))
            filtered_items = [
                item for item in filtered_items
                if datetime.fromisoformat(item.get('created_at', '1970-01-01T00:00:00').replace('Z', '+00:00')) >= date_from
            ]
        
        if filters.get('date_to'):
            date_to = datetime.fromisoformat(filters['date_to'].replace('Z', '+00:00'))
            filtered_items = [
                item for item in filtered_items
                if datetime.fromisoformat(item.get('created_at', '1970-01-01T00:00:00').replace('Z', '+00:00')) <= date_to
            ]
        
        # Sort results
        sort_by = filters.get('sort_by', 'created_at')
        sort_order = filters.get('sort_order', 'desc')
        
        if sort_by == 'value':
            filtered_items.sort(key=lambda x: float(x.get('estimated_value', 0)), reverse=(sort_order == 'desc'))
        elif sort_by == 'name':
            filtered_items.sort(key=lambda x: x.get('name', '').lower(), reverse=(sort_order == 'desc'))
        elif sort_by == 'category':
            filtered_items.sort(key=lambda x: x.get('category', '').lower(), reverse=(sort_order == 'desc'))
        elif sort_by == 'created_at':
            filtered_items.sort(key=lambda x: x.get('created_at', ''), reverse=(sort_order == 'desc'))
        
        return filtered_items
        
    except Exception as e:
        logger.error(f"Error applying filters: {str(e)}")
        return items

def get_inventory_statistics(user_id):
    """Get comprehensive inventory statistics for filtering UI"""
    try:
        user_items = [item for item in inventory_storage.values() if item.get('user_id') == user_id]
        
        if not user_items:
            return {}
        
        # Calculate statistics
        categories = {}
        rooms = {}
        conditions = {}
        value_ranges = {'0-100': 0, '100-500': 0, '500-1000': 0, '1000+': 0}
        
        total_value = 0
        for_sale_count = 0
        
        for item in user_items:
            # Categories
            category = item.get('category', 'Uncategorized')
            categories[category] = categories.get(category, 0) + 1
            
            # Rooms
            room = item.get('room', 'Unassigned')
            rooms[room] = rooms.get(room, 0) + 1
            
            # Conditions
            condition = item.get('condition', 'Good')
            conditions[condition] = conditions.get(condition, 0) + 1
            
            # Value ranges
            value = float(item.get('estimated_value', 0))
            total_value += value
            
            if value <= 100:
                value_ranges['0-100'] += 1
            elif value <= 500:
                value_ranges['100-500'] += 1
            elif value <= 1000:
                value_ranges['500-1000'] += 1
            else:
                value_ranges['1000+'] += 1
            
            # For sale count
            if item.get('for_sale', False):
                for_sale_count += 1
        
        return {
            'total_items': len(user_items),
            'total_value': total_value,
            'for_sale_count': for_sale_count,
            'categories': dict(sorted(categories.items())),
            'rooms': dict(sorted(rooms.items())),
            'conditions': dict(sorted(conditions.items())),
            'value_ranges': value_ranges
        }
        
    except Exception as e:
        logger.error(f"Error getting inventory statistics: {str(e)}")
        return {}

# ===== SEARCH & FILTERING ENDPOINTS =====

@app.route('/api/inventory/search', methods=['POST'])
@require_auth
def search_inventory():
    """Advanced inventory search and filtering"""
    try:
        data = request.get_json()
        user_id = data.get('user_id', 'demo-user')
        filters = data.get('filters', {})
        
        # Get user inventory
        user_items = [item for item in inventory_storage.values() if item.get('user_id') == user_id]
        
        # Apply filters
        filtered_items = apply_inventory_filters(user_items, filters)
        
        # Pagination
        page = int(data.get('page', 1))
        per_page = int(data.get('per_page', 20))
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        paginated_items = filtered_items[start_idx:end_idx]
        
        return jsonify({
            'success': True,
            'items': paginated_items,
            'total_items': len(filtered_items),
            'total_pages': (len(filtered_items) + per_page - 1) // per_page,
            'current_page': page,
            'per_page': per_page,
            'filters_applied': filters
        })
        
    except Exception as e:
        logger.error(f"Error in inventory search: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Search failed'
        }), 500

@app.route('/api/inventory/statistics', methods=['GET'])
@require_auth
def inventory_statistics():
    """Get inventory statistics for filtering UI"""
    try:
        user_id = request.args.get('user_id', 'demo-user')
        stats = get_inventory_statistics(user_id)
        
        return jsonify({
            'success': True,
            'statistics': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting inventory statistics: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get statistics'
        }), 500

@app.route('/api/inventory/categories', methods=['GET'])
@require_auth
def get_categories():
    """Get all available categories"""
    try:
        user_id = request.args.get('user_id', 'demo-user')
        user_items = [item for item in inventory_storage.values() if item.get('user_id') == user_id]
        
        categories = set()
        for item in user_items:
            category = item.get('category', 'Uncategorized')
            categories.add(category)
        
        # Add common categories if none exist
        if not categories:
            categories = {
                'Furniture', 'Electronics', 'Jewelry', 'Art & Collectibles',
                'Kitchen & Dining', 'Books & Media', 'Clothing & Accessories',
                'Tools & Equipment', 'Decorative Items', 'Antiques'
            }
        
        return jsonify({
            'success': True,
            'categories': sorted(list(categories))
        })
        
    except Exception as e:
        logger.error(f"Error getting categories: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get categories'
        }), 500

@app.route('/api/inventory/rooms', methods=['GET'])
@require_auth
def get_rooms():
    """Get all available rooms"""
    try:
        user_id = request.args.get('user_id', 'demo-user')
        user_items = [item for item in inventory_storage.values() if item.get('user_id') == user_id]
        
        rooms = set()
        for item in user_items:
            room = item.get('room', 'Unassigned')
            rooms.add(room)
        
        # Add common rooms if none exist
        if not rooms:
            rooms = {
                'Living Room', 'Bedroom', 'Kitchen', 'Dining Room',
                'Bathroom', 'Office', 'Garage', 'Basement', 'Attic',
                'Guest Room', 'Family Room', 'Laundry Room'
            }
        
        return jsonify({
            'success': True,
            'rooms': sorted(list(rooms))
        })
        
    except Exception as e:
        logger.error(f"Error getting rooms: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get rooms'
        }), 500

@app.route('/api/inventory/quick-filters', methods=['GET'])
@require_auth
def get_quick_filters():
    """Get predefined quick filter options"""
    try:
        quick_filters = [
            {
                'name': 'High Value Items',
                'description': 'Items worth $1,000 or more',
                'filters': {'min_value': 1000}
            },
            {
                'name': 'For Sale Items',
                'description': 'Items currently marked for sale',
                'filters': {'for_sale': True}
            },
            {
                'name': 'Recent Additions',
                'description': 'Items added in the last 30 days',
                'filters': {'date_from': (datetime.now() - timedelta(days=30)).isoformat()}
            },
            {
                'name': 'Jewelry & Valuables',
                'description': 'Jewelry, watches, and precious items',
                'filters': {'category': 'Jewelry'}
            },
            {
                'name': 'Electronics',
                'description': 'All electronic devices and gadgets',
                'filters': {'category': 'Electronics'}
            },
            {
                'name': 'Furniture',
                'description': 'All furniture items',
                'filters': {'category': 'Furniture'}
            },
            {
                'name': 'Excellent Condition',
                'description': 'Items in excellent condition',
                'filters': {'condition': 'Excellent'}
            },
            {
                'name': 'Needs Attention',
                'description': 'Items in poor or fair condition',
                'filters': {'condition': 'Poor'}
            }
        ]
        
        return jsonify({
            'success': True,
            'quick_filters': quick_filters
        })
        
    except Exception as e:
        logger.error(f"Error getting quick filters: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get quick filters'
        }), 500

# ===== CONFLICT RESOLUTION SYSTEM =====

# Conflict resolution storage
conflict_storage = {}
resolution_storage = {}

def detect_item_conflicts(item_id):
    """Detect conflicts for a specific item across estates"""
    try:
        conflicts = []

        estates = family_storage.get('estates', {})
        for estate_id, estate_data in estates.items():
            interested_members = []
            members = estate_data.get('members', {})

            for member_code, wanted_list in estate_data.get('wanted_items', {}).items():
                member_info = members.get(member_code, {})
                for wanted in wanted_list:
                    if wanted.get('item_id') == item_id:
                        interested_members.append({
                            'member_id': member_code,
                            'member_code': member_code,
                            'email': member_info.get('email'),
                            'priority': wanted.get('priority', 'Medium'),
                            'desire_level': wanted.get('desire_level', 3),
                            'notes': wanted.get('notes', ''),
                            'wanted_at': wanted.get('wanted_at')
                        })

            # If more than one person wants it within this estate, capture conflict
            if len(interested_members) > 1:
                conflict_id = f"conflict_{estate_id}_{item_id}_{int(time.time())}"

                conflict = {
                    'conflict_id': conflict_id,
                    'estate_id': estate_id,
                    'item_id': item_id,
                    'interested_members': interested_members,
                    'status': 'active',
                    'created_at': datetime.now().isoformat(),
                    'resolution_method': None,
                    'resolved_at': None,
                    'resolved_by': None,
                    'resolution_notes': '',
                    'discussion_messages': []
                }

                conflict_storage[conflict_id] = conflict
                conflicts.append(conflict)

        return conflicts

    except Exception as e:
        logger.error(f"Error detecting conflicts: {str(e)}")
        return []

def suggest_resolution_methods(conflict):
    """Suggest fair resolution methods for a conflict"""
    try:
        interested_members = conflict.get('interested_members', [])
        num_members = len(interested_members)
        
        suggestions = []
        
        # Priority-based resolution
        high_priority = [m for m in interested_members if m.get('priority') == 'High']
        if len(high_priority) == 1:
            suggestions.append({
                'method': 'priority_based',
                'title': 'Priority-Based Resolution',
                'description': f"{high_priority[0]['member_code']} has marked this as high priority",
                'recommended_recipient': high_priority[0]['member_code'],
                'fairness_score': 85
            })
        
        # Random selection
        suggestions.append({
            'method': 'random_selection',
            'title': 'Random Selection',
            'description': 'Fair random selection among all interested parties',
            'recommended_recipient': 'Random selection needed',
            'fairness_score': 90
        })
        
        # Rotation system
        suggestions.append({
            'method': 'rotation',
            'title': 'Rotation System',
            'description': 'Take turns based on previous selections',
            'recommended_recipient': 'Based on rotation order',
            'fairness_score': 95
        })
        
        # Monetary compensation
        if num_members == 2:
            suggestions.append({
                'method': 'compensation',
                'title': 'Monetary Compensation',
                'description': 'One person gets item, pays others their share of value',
                'recommended_recipient': 'Highest bidder',
                'fairness_score': 80
            })
        
        # Shared ownership
        suggestions.append({
            'method': 'shared_ownership',
            'title': 'Shared Ownership',
            'description': 'Multiple people share ownership/usage',
            'recommended_recipient': 'All interested parties',
            'fairness_score': 75
        })
        
        # Family discussion
        suggestions.append({
            'method': 'family_discussion',
            'title': 'Family Discussion',
            'description': 'Let family members discuss and decide together',
            'recommended_recipient': 'To be decided',
            'fairness_score': 70
        })
        
        # Sort by fairness score
        suggestions.sort(key=lambda x: x['fairness_score'], reverse=True)
        
        return suggestions
        
    except Exception as e:
        logger.error(f"Error suggesting resolution methods: {str(e)}")
        return []

def calculate_fairness_metrics(estate_id: str):
    """Calculate fairness metrics for family distribution within an estate"""
    try:
        estate_data = get_family_estate_data(estate_id)

        # Get all resolved conflicts for this estate
        resolved_conflicts = [
            c for c in conflict_storage.values()
            if c.get('status') == 'resolved' and c.get('estate_id') == estate_id
        ]

        if not resolved_conflicts:
            return {}

        # Count items received by each member
        member_counts = {}
        total_value_received = {}

        for conflict in resolved_conflicts:
            recipient = conflict.get('resolved_recipient')
            if recipient:
                member_counts[recipient] = member_counts.get(recipient, 0) + 1

                # Get item value
                item_id = conflict.get('item_id')
                item = inventory_storage.get(item_id, {})
                if item.get('estate_id') != estate_id:
                    continue
                value = float(item.get('estimated_value', item.get('estimatedValue', 0)))
                total_value_received[recipient] = total_value_received.get(recipient, 0) + value

        # Calculate fairness scores
        total_items = sum(member_counts.values())
        total_value = sum(total_value_received.values())

        fairness_metrics = {
            'total_resolved_conflicts': len(resolved_conflicts),
            'member_distribution': member_counts,
            'value_distribution': total_value_received,
            'fairness_score': 0,
            'recommendations': []
        }

        if total_items > 0 and member_counts:
            # Calculate distribution fairness (closer to equal = higher score)
            expected_per_member = total_items / len(member_counts)
            variance = sum((count - expected_per_member) ** 2 for count in member_counts.values())
            fairness_score = max(0, 100 - (variance * 10))  # Simple fairness calculation

            fairness_metrics['fairness_score'] = round(fairness_score, 1)

            # Generate recommendations
            if fairness_score < 70:
                fairness_metrics['recommendations'].append(
                    "Consider using rotation system for future conflicts to improve fairness"
                )

            # Check for members who haven't received anything
            all_members = set(estate_data.get('members', {}).keys())
            recipients = set(member_counts.keys())
            left_out = all_members - recipients

            if left_out:
                fairness_metrics['recommendations'].append(
                    f"Consider prioritizing {', '.join(left_out)} in future distributions"
                )

        return fairness_metrics

    except Exception as e:
        logger.error(f"Error calculating fairness metrics: {str(e)}")
        return {}

# ===== CONFLICT RESOLUTION ENDPOINTS =====

@app.route('/api/conflicts/detect', methods=['POST'])
@require_auth
def detect_conflicts():
    """Detect conflicts for all items or specific item within the current estate"""
    try:
        estate_id = get_current_estate_id()
        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        data = request.get_json()
        item_id = data.get('item_id')  # Optional: check specific item

        all_conflicts = []

        if item_id:
            # Check specific item
            conflicts = [conflict for conflict in detect_item_conflicts(item_id) if conflict.get('estate_id') == estate_id]
            all_conflicts.extend(conflicts)
        else:
            # Check all items for this estate
            estate_items = [item for item in inventory_storage.values() if item.get('estate_id') == estate_id]
            for item in estate_items:
                conflicts = [conflict for conflict in detect_item_conflicts(item['id']) if conflict.get('estate_id') == estate_id]
                all_conflicts.extend(conflicts)

        return jsonify({
            'success': True,
            'conflicts': all_conflicts,
            'total_conflicts': len(all_conflicts)
        })

    except Exception as e:
        logger.error(f"Error detecting conflicts: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to detect conflicts'
        }), 500

@app.route('/api/conflicts/list', methods=['GET'])
@require_auth
def list_conflicts():
    """Get all active conflicts for current estate"""
    try:
        estate_id = get_current_estate_id()
        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        status = request.args.get('status', 'active')  # active, resolved, all

        conflicts = []
        for conflict in conflict_storage.values():
            if conflict.get('estate_id') != estate_id:
                continue
            if status != 'all' and conflict.get('status') != status:
                continue

            # Add item details
            item_id = conflict.get('item_id')
            item = inventory_storage.get(item_id, {})

            conflict_with_item = conflict.copy()
            conflict_with_item['item_details'] = {
                'name': item.get('name', 'Unknown Item'),
                'category': item.get('category', 'Uncategorized'),
                'estimated_value': item.get('estimated_value', 0),
                'photo_url': item.get('photo_url', '')
            }

            # Add resolution suggestions if active
            if conflict.get('status') == 'active':
                conflict_with_item['resolution_suggestions'] = suggest_resolution_methods(conflict)

            conflicts.append(conflict_with_item)

        # Sort by creation date (newest first)
        conflicts.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        return jsonify({
            'success': True,
            'conflicts': conflicts,
            'total_conflicts': len(conflicts)
        })

    except Exception as e:
        logger.error(f"Error listing conflicts: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to list conflicts'
        }), 500

@app.route('/api/conflicts/resolve', methods=['POST'])
@require_auth
def resolve_conflict():
    """Resolve a conflict with chosen method"""
    try:
        data = request.get_json()
        conflict_id = data.get('conflict_id')
        resolution_method = data.get('resolution_method')
        recipient = data.get('recipient')
        notes = data.get('notes', '')
        resolved_by = data.get('resolved_by', 'Owner')
        
        if not conflict_id or conflict_id not in conflict_storage:
            return jsonify({
                'success': False,
                'error': 'Conflict not found'
            }), 404
        
        conflict = conflict_storage[conflict_id]
        
        estate_id = get_current_estate_id()
        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        if conflict.get('estate_id') != estate_id:
            return jsonify({'success': False, 'error': 'Conflict not part of selected estate'}), 403
        
        # Update conflict status
        conflict['status'] = 'resolved'
        conflict['resolution_method'] = resolution_method
        conflict['resolved_recipient'] = recipient
        conflict['resolved_at'] = datetime.now().isoformat()
        conflict['resolved_by'] = resolved_by
        conflict['resolution_notes'] = notes
        
        # Store resolution
        resolution_id = f"resolution_{conflict_id}_{int(time.time())}"
        resolution_storage[resolution_id] = {
            'resolution_id': resolution_id,
            'conflict_id': conflict_id,
            'item_id': conflict['item_id'],
            'resolution_method': resolution_method,
            'recipient': recipient,
            'resolved_by': resolved_by,
            'resolved_at': datetime.now().isoformat(),
            'notes': notes,
            'interested_members': conflict['interested_members']
        }
        
        # Send notifications to all interested parties
        item = inventory_storage.get(conflict['item_id'], {})
        item_name = item.get('name', 'Unknown Item')
        
        for member in conflict['interested_members']:
            email = member.get('email')
            if email:
                try:
                    send_conflict_resolution_email(
                        email, 
                        member['member_code'], 
                        item_name, 
                        recipient, 
                        resolution_method,
                        notes
                    )
                except Exception as e:
                    logger.error(f"Failed to send resolution email to {email}: {str(e)}")
        
        return jsonify({
            'success': True,
            'message': 'Conflict resolved successfully',
            'resolution_id': resolution_id
        })
        
    except Exception as e:
        logger.error(f"Error resolving conflict: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to resolve conflict'
        }), 500

@app.route('/api/conflicts/discussion', methods=['POST'])
@require_auth
def add_discussion_message():
    """Add message to conflict discussion"""
    try:
        data = request.get_json()
        conflict_id = data.get('conflict_id')
        message = data.get('message')
        author = data.get('author', 'Owner')
        
        if not conflict_id or conflict_id not in conflict_storage:
            return jsonify({
                'success': False,
                'error': 'Conflict not found'
            }), 404
        
        conflict = conflict_storage[conflict_id]
        
        # Add message to discussion
        discussion_message = {
            'message_id': f"msg_{int(time.time())}_{len(conflict.get('discussion_messages', []))}",
            'author': author,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        
        if 'discussion_messages' not in conflict:
            conflict['discussion_messages'] = []
        
        conflict['discussion_messages'].append(discussion_message)
        
        return jsonify({
            'success': True,
            'message': 'Discussion message added',
            'message_id': discussion_message['message_id']
        })
        
    except Exception as e:
        logger.error(f"Error adding discussion message: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to add message'
        }), 500

@app.route('/api/conflicts/fairness', methods=['GET'])
@require_auth
def get_fairness_metrics():
    """Get fairness metrics for family distribution"""
    try:
        estate_id = get_current_estate_id()
        if not estate_id:
            return jsonify({'success': False, 'error': 'No estate selected'}), 400

        metrics = calculate_fairness_metrics(estate_id)

        return jsonify({
            'success': True,
            'fairness_metrics': metrics
        })

    except Exception as e:
        logger.error(f"Error getting fairness metrics: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get fairness metrics'
        }), 500

def send_conflict_resolution_email(email, member_code, item_name, recipient, method, notes):
    """Send conflict resolution notification email"""
    try:
        subject = f"MyEstateAlly - Conflict Resolved: {item_name}"
        
        if recipient == member_code:
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; text-align: center;">
                    <h1 style="color: white; margin: 0;">🎉 Great News!</h1>
                </div>
                
                <div style="padding: 30px; background-color: #f8f9fa;">
                    <h2 style="color: #333;">You've Been Selected!</h2>
                    
                    <p>Dear Family Member {member_code},</p>
                    
                    <p>We're pleased to inform you that the conflict for <strong>{item_name}</strong> has been resolved, and you have been selected to receive this item!</p>
                    
                    <div style="background-color: #e8f5e8; padding: 15px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="color: #2d5a2d; margin-top: 0;">Resolution Details:</h3>
                        <p><strong>Item:</strong> {item_name}</p>
                        <p><strong>Resolution Method:</strong> {method.replace('_', ' ').title()}</p>
                        <p><strong>Selected Recipient:</strong> {recipient}</p>
                        {f'<p><strong>Notes:</strong> {notes}</p>' if notes else ''}
                    </div>
                    
                    <p>Please coordinate with the estate owner for item pickup or delivery arrangements.</p>
                    
                    <p style="margin-top: 30px;">
                        Best regards,<br>
                        <strong>MyEstateAlly Team</strong>
                    </p>
                </div>
            </body>
            </html>
            """
        else:
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; text-align: center;">
                    <h1 style="color: white; margin: 0;">📋 Conflict Resolved</h1>
                </div>
                
                <div style="padding: 30px; background-color: #f8f9fa;">
                    <h2 style="color: #333;">Resolution Update</h2>
                    
                    <p>Dear Family Member {member_code},</p>
                    
                    <p>The conflict for <strong>{item_name}</strong> has been resolved. While you weren't selected for this item, we wanted to keep you informed of the decision.</p>
                    
                    <div style="background-color: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="color: #856404; margin-top: 0;">Resolution Details:</h3>
                        <p><strong>Item:</strong> {item_name}</p>
                        <p><strong>Resolution Method:</strong> {method.replace('_', ' ').title()}</p>
                        <p><strong>Selected Recipient:</strong> {recipient}</p>
                        {f'<p><strong>Notes:</strong> {notes}</p>' if notes else ''}
                    </div>
                    
                    <p>Thank you for your understanding. There will be more opportunities to express interest in other items.</p>
                    
                    <p style="margin-top: 30px;">
                        Best regards,<br>
                        <strong>MyEstateAlly Team</strong>
                    </p>
                </div>
            </body>
            </html>
            """
        
        msg = Message(
            subject=subject,
            recipients=[email],
            html=body,
            sender=app.config['MAIL_DEFAULT_SENDER']
        )
        
        mail.send(msg)
        
    except Exception as e:
        logger.error(f"Error sending conflict resolution email: {str(e)}")
        raise

# ===== ERROR HANDLERS =====

@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': 'Not found'}), 404

# Note: OAuth is configured at the top of this file (lines 125-149)
# Check if OAuth is properly configured
_oauth_ready = False
try:
    # Use same method as OAuth initialization: try env var first, then Secret Manager
    google_client_id = os.environ.get('GOOGLE_CLIENT_ID') or get_secret('GOOGLE_CLIENT_ID') or ''
    google_client_secret = os.environ.get('GOOGLE_CLIENT_SECRET') or get_secret('GOOGLE_CLIENT_SECRET') or ''

    if google_client_id and google_client_secret and google_client_id != 'your-google-client-id':
        _oauth_ready = True
        logger.info(f"OAuth ready check passed - client_id present: {bool(google_client_id)}, secret present: {bool(google_client_secret)}")
    else:
        logger.warning("Google OAuth credentials not properly configured")
except Exception as e:
    logger.error(f"OAuth check failed: {e}")
    _oauth_ready = False

@app.route('/auth/google/login')
def auth_google_login():
    # Check if Google OAuth is configured
    if not google:
        logger.warning("Google OAuth login attempted but not configured")
        return jsonify({'success': False, 'error': 'Google OAuth not configured - please use email/password login'}), 400

    logger.info(f"Google OAuth login requested. OAuth ready: {_oauth_ready}")
    if not oauth or not _oauth_ready:
        return jsonify({'success': False, 'error': 'Google OAuth not configured'}), 400
    if 'google' not in oauth._clients:
        return jsonify({'success': False, 'error': 'Google OAuth client not registered'}), 400

    try:
        # Clean up any old OAuth state tokens from previous failed attempts
        session_keys_to_remove = [key for key in session.keys() if key.startswith('_state_google_')]
        for key in session_keys_to_remove:
            session.pop(key, None)

        session.permanent = True  # Ensure the state cookie survives the round-trip to Google and back
        redirect_uri = OAUTH_CONFIG['google']['redirect_uri'] or url_for('auth_google_callback', _external=True)
        logger.info(f"Redirecting to Google OAuth with redirect_uri: {redirect_uri}")
        return oauth.google.authorize_redirect(redirect_uri)
    except Exception as e:
        logger.error(f"Google OAuth redirect failed: {e}")
        return jsonify({'success': False, 'error': f'OAuth redirect failed: {str(e)}'}), 500

@app.route('/auth/google/callback')
def auth_google_callback():
    # Check if Google OAuth is configured
    if not google:
        logger.error("Google OAuth callback received but not configured")
        return redirect(url_for('index') + '?error=oauth_not_configured')

    if not oauth or 'google' not in oauth._clients:
        logger.error("Google OAuth not configured or client not registered")
        return jsonify({'success': False, 'error': 'Google OAuth not configured'}), 400
    try:
        # Get access token from OAuth callback
        token = oauth.google.authorize_access_token()
        logger.info(f"Google OAuth token received: {bool(token)}")
        
        # Get user info - use the access token to fetch from Google's userinfo endpoint
        userinfo = None
        access_token = token.get('access_token') if token else None
        
        if not access_token:
            logger.error("No access token in OAuth response")
            return redirect(url_for('index') + '?error=oauth_failed&message=No%20access%20token%20received')
        
        # Method 1: Use authlib's built-in userinfo endpoint (should work automatically)
        try:
            resp = oauth.google.get('userinfo', token=token)
            if resp and resp.status_code == 200:
                userinfo = resp.json()
                logger.info("Successfully retrieved userinfo via authlib endpoint")
        except Exception as e1:
            logger.warning(f"Failed to get userinfo via authlib: {e1}")
        
        # Method 2: Direct API call with requests (fallback)
        if not userinfo:
            try:
                import requests
                headers = {'Authorization': f'Bearer {access_token}'}
                resp = requests.get('https://www.googleapis.com/oauth2/v3/userinfo', headers=headers, timeout=10)
                if resp.status_code == 200:
                    userinfo = resp.json()
                    logger.info("Successfully retrieved userinfo via direct API call")
                else:
                    logger.error(f"Userinfo API returned status {resp.status_code}: {resp.text}")
            except ImportError:
                logger.error("requests library not available for fallback userinfo call")
            except Exception as e2:
                logger.error(f"Direct API call failed: {e2}")
        
        # Method 3: Try to decode ID token if available (last resort)
        if not userinfo and token and 'id_token' in token:
            try:
                # Try using PyJWT to decode the ID token
                try:
                    import jwt as pyjwt
                    id_token = token.get('id_token')
                    if id_token:
                        # Decode without verification since we trust Google's token
                        userinfo = pyjwt.decode(id_token, options={"verify_signature": False})
                        logger.info("Successfully decoded userinfo from ID token")
                except ImportError:
                    logger.warning("PyJWT not available for ID token decoding")
            except Exception as e3:
                logger.warning(f"Failed to decode ID token: {e3}")
        
        if not userinfo:
            error_msg = f"Could not retrieve userinfo. Token available: {bool(token)}"
            logger.error(error_msg)
            # Redirect to login page with error
            return redirect(url_for('index') + '?error=oauth_failed&message=' + error_msg.replace(' ', '%20'))
        
        logger.info(f"Userinfo retrieved: {userinfo.get('email', 'no email')}")
        
        # Get user ID - Google uses 'sub' as the user identifier
        user_id = userinfo.get('sub') or userinfo.get('id')
        if not user_id:
            logger.error(f"Invalid Google response - no user ID found. Userinfo keys: {list(userinfo.keys())}")
            return redirect(url_for('index') + '?error=oauth_failed&message=Invalid%20Google%20response%20-%20no%20user%20ID')
        
        # Get or create user
        existing_user = auth_storage['users'].get(user_id, {})
        user_data = {
            'id': user_id,
            'email': userinfo.get('email', ''),
            'name': userinfo.get('name') or userinfo.get('given_name') or userinfo.get('email', '').split('@')[0],
            'provider': 'google',
            'created_at': existing_user.get('created_at', datetime.now().isoformat()),
            'last_login': datetime.now().isoformat()
        }
        
        # Preserve any existing user data
        if existing_user:
            user_data.update(existing_user)
            user_data['last_login'] = datetime.now().isoformat()

        # Save to Firestore
        storage_service.add_document('users', user_id, user_data)

        # Also save to in-memory storage for compatibility
        auth_storage['users'][user_id] = user_data
        save_auth_storage()

        # Set Flask session (is_authenticated() relies on this, not custom session_id)
        session.permanent = True  # Make session persistent
        session['user_id'] = user_id
        session['user_email'] = user_data['email']
        session.modified = True  # Force Flask to commit session before redirect

        logger.info(f"Session set for user {user_id}: user_id={session.get('user_id')}, email={session.get('user_email')}")

        # Auto-select user's first estate or last used estate
        try:
            logger.info(f"Attempting to get estates for user {user_id}")
            user_estates = get_user_estates(user_id)
            logger.info(f"Found {len(user_estates)} estates for user {user_id}")
            if user_estates:
                # Check if user has a last_used_estate preference
                last_estate_id = user_data.get('last_used_estate')
                if last_estate_id and any(e['id'] == last_estate_id for e in user_estates):
                    session['current_estate_id'] = last_estate_id
                    session['estate_id'] = last_estate_id
                    logger.info(f"Auto-selected last used estate: {last_estate_id}")
                else:
                    # Default to first estate
                    session['current_estate_id'] = user_estates[0]['id']
                    session['estate_id'] = user_estates[0]['id']
                    logger.info(f"Auto-selected first estate: {user_estates[0]['id']}")
        except Exception as e:
            logger.warning(f"Could not auto-select estate: {e}")
            # Don't fail login if estate selection fails

        logger.info(f"Google login successful for user: {user_data['email']}")

        # Clean up OAuth state tokens after successful login
        session_keys_to_remove = [key for key in list(session.keys()) if key.startswith('_state_google_')]
        for key in session_keys_to_remove:
            session.pop(key, None)

        # Return redirect directly - Flask will automatically add session cookie
        # with the correct SameSite/Secure flags from app.config
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}", exc_info=True)
        # Redirect to login page with error message instead of returning JSON
        error_msg = str(e).replace(' ', '%20').replace('&', '%26')
        return redirect(url_for('index') + f'?error=oauth_failed&message={error_msg}')

@app.route('/auth/logout', methods=['POST'])
def auth_logout():
    session_id = request.cookies.get('session_id')
    if session_id and session_id in auth_storage['sessions']:
        del auth_storage['sessions'][session_id]
    resp = jsonify({'success': True})
    resp.set_cookie('session_id', '', expires=0)
    return resp

@app.route('/api/family/desire-analysis/<share_id>', methods=['GET'])
def get_desire_analysis(share_id):
    """Get desire analysis for property owner decision making"""
    try:
        estate_id, estate_data, share_link = get_share_link_context(share_id)
        if not estate_id or not share_link:
            return jsonify({
                'success': False,
                'error': 'Invalid share link'
            }), 404

        # Get all wanted items with desire levels
        wanted_items = estate_data.get('wanted_items', {})
        members = estate_data.get('members', {})
        
        # Analyze desire levels by item
        item_desires = {}
        for member_code, member_wanted in wanted_items.items():
            member_name = members.get(member_code, {}).get('name', f'Member {member_code[:8]}')
            for wanted_item in member_wanted:
                item_id = wanted_item['item_id']
                if item_id not in item_desires:
                    item_desires[item_id] = {
                        'item_id': item_id,
                        'desires': [],
                        'total_desire': 0,
                        'max_desire': 0,
                        'desire_count': 0
                    }
                
                desire_level = wanted_item.get('desire_level', 3)
                item_desires[item_id]['desires'].append({
                    'member_code': member_code,
                    'member_name': member_name,
                    'desire_level': desire_level,
                    'priority': wanted_item.get('priority', 'medium'),
                    'wanted_at': wanted_item.get('wanted_at', '')
                })
                item_desires[item_id]['total_desire'] += desire_level
                item_desires[item_id]['max_desire'] = max(item_desires[item_id]['max_desire'], desire_level)
                item_desires[item_id]['desire_count'] += 1
        
        # Get item details and sort by total desire
        analysis_items = []
        for item_id, desire_data in item_desires.items():
            if item_id in inventory_storage:
                item = inventory_storage[item_id]
                analysis_items.append({
                    'item': item,
                    'desire_analysis': desire_data,
                    'average_desire': round(desire_data['total_desire'] / desire_data['desire_count'], 1),
                    'conflict_level': 'high' if desire_data['desire_count'] > 1 else 'none'
                })
        
        # Sort by total desire (highest first)
        analysis_items.sort(key=lambda x: x['desire_analysis']['total_desire'], reverse=True)
        
        return jsonify({
            'success': True,
            'analysis': analysis_items,
            'summary': {
                'total_items_with_desires': len(analysis_items),
                'high_conflict_items': len([i for i in analysis_items if i['conflict_level'] == 'high']),
                'total_family_members': len(members)
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting desire analysis: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get desire analysis'
        }), 500

@app.route('/api/family/assign-item/<share_id>', methods=['POST'])
def assign_item(share_id):
    """Assign an item to a family member (property owner decision)"""
    try:
        estate_id, estate_data, share_link = get_share_link_context(share_id)
        if not estate_id or not share_link:
            return jsonify({
                'success': False,
                'error': 'Invalid share link'
            }), 404

        data = request.get_json()
        item_id = data.get('item_id')
        assigned_to = data.get('assigned_to')  # member_code
        decision_reason = data.get('reason', '')
        
        if not item_id or not assigned_to:
            return jsonify({
                'success': False,
                'error': 'Item ID and assigned member required'
            }), 400
        
        if assigned_to not in estate_data['members']:
            return jsonify({
                'success': False,
                'error': 'Assigned member not found in this estate'
            }), 400
        
        # Update item assignment
        item = inventory_storage.get(item_id)
        if item and item.get('estate_id') == estate_id:
            item['assignedTo'] = assigned_to
            item['assignment_reason'] = decision_reason
            item['assigned_at'] = datetime.now().isoformat()
            item['lastModified'] = datetime.now().isoformat()
            item['status'] = 'assigned'  # Track item status
            
            # Try to save to Firestore
            try:
                firestore_update_inventory_item(item)
            except:
                # Fall back to JSON storage
                save_storage('inventory.json', inventory_storage)
            
            # Log the assignment decision
            estate_data.setdefault('assignment_decisions', []).append({
                'item_id': item_id,
                'assigned_to': assigned_to,
                'reason': decision_reason,
                'assigned_at': datetime.now().isoformat(),
                'share_id': share_id
            })
            # Save changes to Firestore
            firestore_update_family_data(estate_id, {'assignment_decisions': estate_data['assignment_decisions']})
            
            return jsonify({
                'success': True,
                'message': 'Item assigned successfully',
                'assignment': {
                    'item_id': item_id,
                    'assigned_to': assigned_to,
                    'reason': decision_reason,
                    'assigned_at': datetime.now().isoformat()
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Item not found'
            }), 404
        
    except Exception as e:
        logger.error(f"Error assigning item: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to assign item'
        }), 500

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Create upload directory (Windows compatible)
    import tempfile
    upload_dir = os.path.join(tempfile.gettempdir(), 'uploads')
    os.makedirs(upload_dir, exist_ok=True)

    # Run the app - NEVER enable debug mode in production (security risk)
    is_production = os.environ.get('GAE_ENV') is not None
    app.run(host='0.0.0.0', port=8080, debug=not is_production)

