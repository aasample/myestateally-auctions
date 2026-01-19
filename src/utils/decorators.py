"""
Flask route decorators for authentication and authorization
"""
from functools import wraps
from flask import jsonify, session


def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        # Check if user is admin (you can implement this based on your user model)
        user_id = session.get('user_id')
        # For now, just check authentication
        # TODO: Add actual admin check from user data

        return f(*args, **kwargs)
    return decorated_function
