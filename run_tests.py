#!/usr/bin/env python3
"""
Test runner for MyEstateAlly test suite
"""
import unittest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))


def run_tests(verbose=True):
    """Run all tests"""
    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = 'tests'
    suite = loader.discover(start_dir, pattern='test_*.py')

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2 if verbose else 1)
    result = runner.run(suite)

    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    exit_code = run_tests(verbose)
    sys.exit(exit_code)
