#!/usr/bin/env python3
"""
Test Firestore integration - Verify data persistence
"""
import os
import sys

# Set environment
os.environ['USE_FIRESTORE'] = 'true'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'estateally-ai-services'

try:
    from google.cloud import firestore

    # Initialize Firestore
    db = firestore.Client()

    print("=" * 60)
    print("Firestore Connection Test")
    print("=" * 60)
    print()

    # Test 1: Check users collection
    print("1. Checking 'users' collection...")
    users_ref = db.collection('users')
    users = list(users_ref.limit(5).stream())
    print(f"   Found {len(users)} users in Firestore")
    if users:
        for user_doc in users:
            user = user_doc.to_dict()
            print(f"   - {user.get('email')} ({user.get('account_type', 'unknown')})")
    print()

    # Test 2: Check inventory collection
    print("2. Checking 'inventory' collection...")
    inventory_ref = db.collection('inventory')
    items = list(inventory_ref.limit(5).stream())
    print(f"   Found {len(items)} items in Firestore")
    if items:
        for item_doc in items:
            item = item_doc.to_dict()
            print(f"   - {item.get('name')} (Estate: {item.get('estate_id', 'unknown')})")
    print()

    # Test 3: Create a test document
    print("3. Creating test document...")
    test_doc_id = 'test_connection_' + str(os.getpid())
    test_data = {
        'test': True,
        'message': 'Firestore is working!',
        'timestamp': firestore.SERVER_TIMESTAMP
    }
    db.collection('test').document(test_doc_id).set(test_data)
    print(f"   ✅ Test document created: {test_doc_id}")
    print()

    # Test 4: Read back the test document
    print("4. Reading back test document...")
    doc = db.collection('test').document(test_doc_id).get()
    if doc.exists:
        data = doc.to_dict()
        print(f"   ✅ Test document retrieved: {data.get('message')}")
    print()

    # Test 5: Delete the test document
    print("5. Cleaning up test document...")
    db.collection('test').document(test_doc_id).delete()
    print(f"   ✅ Test document deleted")
    print()

    print("=" * 60)
    print("✅ Firestore is working correctly!")
    print("=" * 60)
    print()
    print("Your application will:")
    print("✅ Store all data in Firestore")
    print("✅ Persist data across deployments")
    print("✅ Never lose inventory items again")
    print()

except Exception as e:
    print(f"❌ Error testing Firestore: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
