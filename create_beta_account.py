#!/usr/bin/env python3
"""
Create a beta tester account for MyEstateAlly
Usage: python create_beta_account.py
"""
import os
import sys
import uuid
from datetime import datetime

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Set environment to use Firestore
os.environ['USE_FIRESTORE'] = 'true'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'estateally-ai-services'

from utils.auth_helpers import hash_password

def create_beta_account(email, name, temporary_password):
    """Create a beta tester account"""
    from google.cloud import firestore

    db = firestore.Client()

    # Check if user already exists
    users_ref = db.collection('users')
    query = users_ref.where('email', '==', email.lower()).limit(1)
    existing = list(query.stream())

    if existing:
        print(f"❌ User with email {email} already exists!")
        return None

    # Create new user
    user_id = f"user_{uuid.uuid4().hex[:16]}"
    user_data = {
        'id': user_id,
        'email': email.lower(),
        'name': name,
        'password_hash': hash_password(temporary_password),
        'account_type': 'beta',
        'grandfathered': True,
        'stripe_customer_id': None,
        'provider': 'email',
        'created_at': datetime.now().isoformat(),
        'last_login': datetime.now().isoformat(),
        'mfa_enabled': False,
        'beta_tester': True,
        'notes': 'Family beta tester - free lifetime access'
    }

    # Save to Firestore
    db.collection('users').document(user_id).set(user_data)

    print(f"✅ Beta account created successfully!")
    print(f"   Email: {email}")
    print(f"   Name: {name}")
    print(f"   Temporary Password: {temporary_password}")
    print(f"   Account Type: beta (grandfathered)")
    print(f"\nSend this info to the user and ask them to change their password after first login.")

    return user_id


def main():
    """Interactive beta account creation"""
    print("=" * 60)
    print("MyEstateAlly - Beta Tester Account Creation")
    print("=" * 60)
    print()

    # Get user input
    email = input("Enter email address: ").strip()
    if not email or '@' not in email:
        print("❌ Invalid email address")
        return

    name = input("Enter full name: ").strip()
    if not name:
        name = email.split('@')[0].title()

    # Generate temporary password
    import secrets
    temporary_password = secrets.token_urlsafe(12)

    print()
    print(f"Creating beta account for:")
    print(f"  Email: {email}")
    print(f"  Name: {name}")
    print(f"  Temporary Password: {temporary_password}")
    print()

    confirm = input("Create this account? (yes/no): ").strip().lower()
    if confirm not in ['yes', 'y']:
        print("❌ Cancelled")
        return

    # Create the account
    try:
        user_id = create_beta_account(email, name, temporary_password)
        if user_id:
            print()
            print("=" * 60)
            print("WELCOME EMAIL TEMPLATE")
            print("=" * 60)
            print(f"""
Subject: You're invited to beta test MyEstateAlly! 🎉

Hi {name},

You're invited to be one of the first people to test MyEstateAlly -
an AI-powered estate inventory management tool!

**Your Beta Access:**
- URL: https://estateally-ai-services.ue.r.appspot.com
- Email: {email}
- Temporary Password: {temporary_password}
- Status: FREE during beta (and free lifetime access after launch!)

**Please change your password after your first login!**

**What to Test:**
- Create inventory items
- Try the AI pricing (if working)
- Use family sharing features
- Try the mobile QR upload

**We Need Your Feedback:**
- What do you love?
- What's confusing?
- What features are missing?
- Any bugs or issues?

As a thank you for testing, you'll get:
✅ Free access during beta
✅ Free lifetime access when we launch (grandfathered)
✅ Early access to new features

Thanks for helping make MyEstateAlly awesome!

- Alicia
""")
    except Exception as e:
        print(f"❌ Error creating account: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
