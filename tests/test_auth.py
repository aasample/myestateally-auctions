"""
Unit tests for authentication utilities
"""
import unittest
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.auth_helpers import hash_password, verify_password


class TestAuthHelpers(unittest.TestCase):
    """Test authentication helper functions"""

    def test_hash_password(self):
        """Test password hashing"""
        password = "test_password_123"
        hashed = hash_password(password)

        # Hash should not equal original password
        self.assertNotEqual(password, hashed)

        # Hash should be a string
        self.assertIsInstance(hashed, str)

        # Hash should not be empty
        self.assertGreater(len(hashed), 0)

    def test_verify_password_correct(self):
        """Test password verification with correct password"""
        password = "correct_password"
        hashed = hash_password(password)

        # Verification should succeed
        self.assertTrue(verify_password(password, hashed))

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password"""
        password = "correct_password"
        wrong_password = "wrong_password"
        hashed = hash_password(password)

        # Verification should fail
        self.assertFalse(verify_password(wrong_password, hashed))

    def test_hash_password_consistency(self):
        """Test that same password produces verifiable hash"""
        password = "test123"

        # Hash password twice
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Hashes might be different (bcrypt uses salt)
        # But both should verify correctly
        self.assertTrue(verify_password(password, hash1))
        self.assertTrue(verify_password(password, hash2))


if __name__ == '__main__':
    unittest.main()
