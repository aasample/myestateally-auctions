"""
Validation utilities for input sanitization and validation
"""

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
    if not email or '@' not in email:
        return False

    parts = email.split('@')
    if len(parts) != 2:
        return False

    local, domain = parts
    if not local or not domain or '.' not in domain:
        return False

    return True


def sanitize_string(value, max_length=500):
    """Sanitize string input to prevent injection attacks"""
    if not isinstance(value, str):
        return str(value)
    # Strip dangerous characters and limit length
    sanitized = value.strip()[:max_length]
    return sanitized


def validate_password_strength(password):
    """
    Validate password meets minimum requirements
    Returns: (is_valid, error_message)
    """
    if len(password) < 6:
        return False, "Password must be at least 6 characters long"

    if len(password) > 128:
        return False, "Password too long"

    return True, None


def validate_numeric_value(value, min_val=0, max_val=999999999):
    """
    Validate and convert numeric value
    Returns: (is_valid, converted_value, error_message)
    """
    try:
        numeric = float(value)
        if numeric < min_val or numeric > max_val:
            return False, 0, f"Value must be between {min_val} and {max_val}"
        return True, numeric, None
    except (ValueError, TypeError):
        return False, 0, "Invalid numeric value"
