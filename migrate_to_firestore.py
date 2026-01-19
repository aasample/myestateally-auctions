#!/usr/bin/env python3
"""
Migration script to move data from JSON files to Firestore
"""
import json
import os
import sys
from datetime import datetime


def migrate_data():
    """Migrate all data from JSON to Firestore"""
    print("=" * 60)
    print("MyEstateAlly - JSON to Firestore Migration Tool")
    print("=" * 60)

    # Check for Firestore credentials
    if not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS') and not os.environ.get('GOOGLE_CLOUD_PROJECT'):
        print("\n❌ Error: Google Cloud credentials not configured")
        print("\nPlease set one of:")
        print("  - GOOGLE_APPLICATION_CREDENTIALS (path to service account key)")
        print("  - Run on App Engine (automatic authentication)")
        print("\nSee MIGRATE_TO_FIRESTORE.md for setup instructions")
        return False

    try:
        from google.cloud import firestore
        db = firestore.Client()
        print("\n✅ Connected to Firestore")
    except Exception as e:
        print(f"\n❌ Failed to connect to Firestore: {e}")
        print("\nMake sure:")
        print("  1. Firestore is enabled in your Google Cloud project")
        print("  2. google-cloud-firestore is installed (pip install google-cloud-firestore)")
        print("  3. Credentials are properly configured")
        return False

    # Track statistics
    stats = {
        'users': 0,
        'estates': 0,
        'items': 0
    }

    # Migrate Users
    print("\n" + "=" * 60)
    print("1. MIGRATING USERS")
    print("=" * 60)

    if os.path.exists('auth.json'):
        try:
            with open('auth.json', 'r') as f:
                auth_data = json.load(f)
                users = auth_data.get('users', {})

            if not users:
                print("   ℹ️  No users found in auth.json")
            else:
                for user_id, user_data in users.items():
                    try:
                        # Add migration metadata
                        user_data['migrated_at'] = datetime.now().isoformat()
                        user_data['migration_source'] = 'json'

                        db.collection('users').document(user_id).set(user_data)
                        email = user_data.get('email', 'unknown')
                        print(f"   ✅ {email} (ID: {user_id[:8]}...)")
                        stats['users'] += 1
                    except Exception as e:
                        print(f"   ❌ Failed to migrate user {user_id}: {e}")

                print(f"\n   📊 Successfully migrated {stats['users']} users")
        except Exception as e:
            print(f"   ❌ Error reading auth.json: {e}")
    else:
        print("   ℹ️  auth.json not found - skipping users")

    # Migrate Estates
    print("\n" + "=" * 60)
    print("2. MIGRATING ESTATES")
    print("=" * 60)

    if os.path.exists('estates.json'):
        try:
            with open('estates.json', 'r') as f:
                estates = json.load(f)

            if not estates:
                print("   ℹ️  No estates found in estates.json")
            else:
                for estate_id, estate_data in estates.items():
                    try:
                        # Add migration metadata
                        estate_data['migrated_at'] = datetime.now().isoformat()
                        estate_data['migration_source'] = 'json'

                        db.collection('estates').document(estate_id).set(estate_data)
                        name = estate_data.get('name', 'Unnamed Estate')
                        print(f"   ✅ {name} (ID: {estate_id[:8]}...)")
                        stats['estates'] += 1
                    except Exception as e:
                        print(f"   ❌ Failed to migrate estate {estate_id}: {e}")

                print(f"\n   📊 Successfully migrated {stats['estates']} estates")
        except Exception as e:
            print(f"   ❌ Error reading estates.json: {e}")
    else:
        print("   ℹ️  estates.json not found - skipping estates")

    # Migrate Inventory Items
    print("\n" + "=" * 60)
    print("3. MIGRATING INVENTORY ITEMS")
    print("=" * 60)

    if os.path.exists('inventory.json'):
        try:
            with open('inventory.json', 'r') as f:
                inventory = json.load(f)

            if not inventory:
                print("   ℹ️  No items found in inventory.json")
            else:
                for item_id, item_data in inventory.items():
                    try:
                        # Add migration metadata
                        item_data['migrated_at'] = datetime.now().isoformat()
                        item_data['migration_source'] = 'json'

                        db.collection('inventory_items').document(item_id).set(item_data)
                        name = item_data.get('name', 'Unnamed Item')
                        print(f"   ✅ {name} (ID: {item_id[:8]}...)")
                        stats['items'] += 1
                    except Exception as e:
                        print(f"   ❌ Failed to migrate item {item_id}: {e}")

                print(f"\n   📊 Successfully migrated {stats['items']} items")
        except Exception as e:
            print(f"   ❌ Error reading inventory.json: {e}")
    else:
        print("   ℹ️  inventory.json not found - skipping items")

    # Summary
    print("\n" + "=" * 60)
    print("MIGRATION SUMMARY")
    print("=" * 60)
    print(f"✅ Users migrated:      {stats['users']}")
    print(f"✅ Estates migrated:    {stats['estates']}")
    print(f"✅ Items migrated:      {stats['items']}")
    print(f"✅ Total documents:     {sum(stats.values())}")

    if sum(stats.values()) > 0:
        print("\n" + "=" * 60)
        print("NEXT STEPS")
        print("=" * 60)
        print("1. ✅ Verify data in Firestore Console:")
        print("   https://console.cloud.google.com/firestore")
        print("\n2. ✅ Test your application locally:")
        print("   Set USE_FIRESTORE=true in .env")
        print("   Run: python run_local.py")
        print("\n3. ✅ Backup your JSON files:")
        print("   mkdir -p backup")
        print("   cp *.json backup/")
        print("\n4. ✅ Update production configuration:")
        print("   Edit app.yaml.production")
        print("   Set USE_FIRESTORE: 'true'")
        print("\n5. ✅ Deploy to production:")
        print("   gcloud app deploy app.yaml.production")

        print("\n" + "=" * 60)
        print("⚠️  IMPORTANT REMINDERS")
        print("=" * 60)
        print("• Keep JSON backups until you verify everything works")
        print("• Monitor Firestore usage in Cloud Console")
        print("• Review MIGRATE_TO_FIRESTORE.md for rollback procedure")
        print("• Set up Firestore security rules for production")

    return True


if __name__ == '__main__':
    print("\n⚠️  This will migrate all data from JSON files to Firestore")
    print("⚠️  Make sure you have backups of your JSON files!\n")

    try:
        response = input("Continue with migration? (yes/no): ").strip().lower()
        if response == 'yes':
            success = migrate_data()
            if success:
                print("\n✅ Migration completed successfully!\n")
                sys.exit(0)
            else:
                print("\n❌ Migration failed. See errors above.\n")
                sys.exit(1)
        else:
            print("\n❌ Migration cancelled by user\n")
            sys.exit(0)
    except KeyboardInterrupt:
        print("\n\n❌ Migration cancelled by user\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
