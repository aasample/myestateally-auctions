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
    Validate password meets security requirements (OWASP recommendations)
    Returns: (is_valid, error_message)
    """
    # Minimum length increased from 6 to 12 for better security
    if len(password) < 12:
        return False, "Password must be at least 12 characters long"

    if len(password) > 128:
        return False, "Password too long (max 128 characters)"

    # Require at least one uppercase letter
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"

    # Require at least one lowercase letter
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"

    # Require at least one digit
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"

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
