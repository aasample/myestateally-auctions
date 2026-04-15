"""
Unit tests for validation utilities
"""
import unittest
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.validation import (
    validate_required_fields,
    validate_email,
    sanitize_string,
    validate_password_strength,
    validate_numeric_value
)


class TestValidation(unittest.TestCase):
    """Test validation utility functions"""

    def test_validate_required_fields_success(self):
        """Test successful validation of required fields"""
        data = {'email': 'test@test.com', 'password': 'pass123'}
        valid, error = validate_required_fields(data, ['email', 'password'])
        self.assertTrue(valid)
        self.assertIsNone(error)

    def test_validate_required_fields_missing(self):
        """Test validation with missing field"""
        data = {'email': 'test@test.com'}
        valid, error = validate_required_fields(data, ['email', 'password'])
        self.assertFalse(valid)
        self.assertIn('password', error)

    def test_validate_required_fields_empty(self):
        """Test validation with empty data"""
        valid, error = validate_required_fields(None, ['email'])
        self.assertFalse(valid)
        self.assertEqual(error, "No data provided")

    def test_validate_email_valid(self):
        """Test valid email addresses"""
        self.assertTrue(validate_email('test@example.com'))
        self.assertTrue(validate_email('user.name+tag@example.co.uk'))

    def test_validate_email_invalid(self):
        """Test invalid email addresses"""
        self.assertFalse(validate_email('invalid'))
        self.assertFalse(validate_email('no-at-sign.com'))
        self.assertFalse(validate_email('@nodomain.com'))
        self.assertFalse(validate_email(''))

    def test_sanitize_string(self):
        """Test string sanitization"""
        # Test whitespace trimming
        result = sanitize_string('  test string  ')
        self.assertEqual(result, 'test string')

        # Test length limiting
        long_string = 'a' * 1000
        result = sanitize_string(long_string, max_length=100)
        self.assertEqual(len(result), 100)

        # Test non-string input
        result = sanitize_string(123)
        self.assertEqual(result, '123')

    def test_validate_password_strength(self):
        """Test password strength validation"""
        # Valid password (12+ chars with upper, lower, digit, special)
        valid, error = validate_password_strength('SecurePass123!')
        self.assertTrue(valid)
        self.assertIsNone(error)

        # Too short
        valid, error = validate_password_strength('12345')
        self.assertFalse(valid)
        self.assertIsNotNone(error)

        # Too long
        valid, error = validate_password_strength('a' * 200)
        self.assertFalse(valid)
        self.assertIn('too long', error)

    def test_validate_numeric_value(self):
        """Test numeric value validation"""
        # Valid value
        valid, value, error = validate_numeric_value(100)
        self.assertTrue(valid)
        self.assertEqual(value, 100.0)
        self.assertIsNone(error)

        # Valid string number
        valid, value, error = validate_numeric_value('250.50')
        self.assertTrue(valid)
        self.assertEqual(value, 250.50)

        # Out of range
        valid, value, error = validate_numeric_value(10000000000)
        self.assertFalse(valid)

        # Invalid value
        valid, value, error = validate_numeric_value('not-a-number')
        self.assertFalse(valid)


if __name__ == '__main__':
    unittest.main()
