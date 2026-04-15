#!/usr/bin/env python3
"""
MyEstateAlly — Agile Test Runner
Runs all sprints and prints a summary report.
"""
import sys
import os
import time

os.environ.setdefault('FLASK_ENV', 'testing')
os.environ.setdefault('USE_FIRESTORE', 'false')
os.environ.setdefault('WTF_CSRF_ENABLED', 'false')


def run():
    try:
        import pytest
    except ImportError:
        print("pytest not found. Install with: pip install -r requirements-test.txt")
        sys.exit(1)

    start = time.time()
    print("\n" + "=" * 60)
    print("  MyEstateAlly — Agile Test Suite")
    print("=" * 60)
    print("\nSprints:")
    print("  Sprint 1 — Authentication")
    print("  Sprint 2 — Inventory CRUD")
    print("  Sprint 3 — Family & Sharing")
    print("  Sprint 4 — AI Features (Gemini)")
    print("  Sprint 5 — Documents")
    print("  Sprint 6 — Estates, QR, Exports, Timeline")
    print("\nRunning...\n")

    args = [
        'tests/',
        '-v',
        '--tb=short',
        '--no-header',
        '--junit-xml=test-results.xml',
    ]

    # Pass through any extra args from command line (e.g. -k "returns_401")
    args += sys.argv[1:]

    exit_code = pytest.main(args)

    elapsed = time.time() - start
    print(f"\nCompleted in {elapsed:.1f}s")
    print("Results saved to: test-results.xml")
    return exit_code


if __name__ == '__main__':
    sys.exit(run())
