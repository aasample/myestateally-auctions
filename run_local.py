#!/usr/bin/env python3
"""
Local Testing Server for MyEstateAlly
Run this script to start the Flask development server locally
"""

import os
import sys

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Set environment variables for local development
os.environ.setdefault('FLASK_ENV', 'development')
os.environ.setdefault('FLASK_DEBUG', 'true')
os.environ.setdefault('SECRET_KEY', 'myestateally-dev-testing-key-2024-local')
os.environ.setdefault('GAE_ENV', '')  # Not running on GAE locally

# Try to load from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Using default environment variables.")

if __name__ == '__main__':
    print("=" * 60)
    print("MyEstateAlly - Local Development Server")
    print("=" * 60)
    print()
    print("Starting Flask server...")
    print("Server will be available at: http://localhost:8080")
    print("Press Ctrl+C to stop the server")
    print()
    print("=" * 60)
    print()
    
    # Import and run the Flask app
    from main import app
    
    # Create upload directory
    import tempfile
    upload_dir = os.path.join(tempfile.gettempdir(), 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    print(f"Upload directory: {upload_dir}")
    print()
    
    # Run the app
    app.run(host='127.0.0.1', port=8080, debug=True)




