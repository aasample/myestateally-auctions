#!/usr/bin/env python3
"""
Migration script: Move data from JSON files to Firestore
Run ONCE before deploying Firestore-only version

Usage:
    python migrate_to_firestore.py
"""

import json
import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from services.storage_service import StorageService

def migrate_inventory():
    """Migrate inventory.json to Firestore"""
    print("📦 Migrating inventory data...")

    if not os.path.exists('inventory.json'):
        print("   No inventory.json found, skipping")
        return 0

    with open('inventory.json', 'r') as f:
        inventory_data = json.load(f)

    service = StorageService(use_firestore=True)
    count = 0

    for item_id, item in inventory_data.items():
        item['id'] = item_id
        if service.add_document('inventory', item_id, item):
            count += 1

    print(f"   ✅ Migrated {count} inventory items")
    return count

def migrate_users():
    """Migrate users from auth.json to Firestore"""
    print("👥 Migrating user data...")

    if not os.path.exists('auth.json'):
        print("   No auth.json found, skipping")
        return 0

    with open('auth.json', 'r') as f:
        auth_data = json.load(f)

    service = StorageService(use_firestore=True)
    count = 0

    users = auth_data.get('users', {})
    for user_id, user in users.items():
        user['id'] = user_id
        if service.add_document('users', user_id, user):
            count += 1

    print(f"   ✅ Migrated {count} users")
    return count

def migrate_estates():
    """Migrate estates.json to Firestore"""
    print("🏠 Migrating estate data...")

    if not os.path.exists('estates.json'):
        print("   No estates.json found, skipping")
        return 0

    with open('estates.json', 'r') as f:
        estate_data = json.load(f)

    service = StorageService(use_firestore=True)
    count = 0

    # Migrate estates
    for estate_id, estate in estate_data.get('estates', {}).items():
        estate['id'] = estate_id
        if service.add_document('estates', estate_id, estate):
            count += 1

    # Update user estate lists
    for user_id, estate_ids in estate_data.get('user_estates', {}).items():
        user = service.get_document('users', user_id)
        if user:
            service.update_document('users', user_id, {'estates': estate_ids})

    print(f"   ✅ Migrated {count} estates")
    return count

def migrate_family_data():
    """Migrate family.json to Firestore"""
    print("👨‍👩‍👧‍👦 Migrating family data...")

    if not os.path.exists('family.json'):
        print("   No family.json found, skipping")
        return 0

    with open('family.json', 'r') as f:
        family_data = json.load(f)

    service = StorageService(use_firestore=True)
    count = 0

    # Migrate estate family data
    for estate_id, data in family_data.get('estates', {}).items():
        doc_id = f"estate_{estate_id}_family"
        data['estate_id'] = estate_id
        data['id'] = doc_id
        data['migrated_at'] = datetime.now().isoformat()
        if service.add_document('family_data', doc_id, data):
            count += 1

    # Migrate share links
    link_count = 0
    for share_id, link in family_data.get('share_links', {}).items():
        link['id'] = share_id
        if service.add_document('share_links', share_id, link):
            link_count += 1

    print(f"   ✅ Migrated {count} family records and {link_count} share links")
    return count + link_count

def create_backups():
    """Create backups of JSON files"""
    print("💾 Creating backups...")

    files = ['inventory.json', 'family.json', 'estates.json', 'auth.json', 'users.json']
    backup_count = 0

    for filename in files:
        if os.path.exists(filename):
            backup_name = f"{filename}.backup"
            with open(filename, 'r') as f:
                data = f.read()
            with open(backup_name, 'w') as f:
                f.write(data)
            print(f"   ✅ Backed up {filename} → {backup_name}")
            backup_count += 1

    return backup_count

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 MyEstateAlly - Firestore Migration Script")
    print("=" * 60)
    print()

    # Step 1: Create backups
    backup_count = create_backups()
    print()

    # Step 2: Migrate data
    total = 0
    total += migrate_users()
    total += migrate_estates()
    total += migrate_inventory()
    total += migrate_family_data()

    print()
    print("=" * 60)
    print(f"✅ Migration complete!")
    print(f"   Total records migrated: {total}")
    print(f"   Backup files created: {backup_count}")
    print("=" * 60)
    print()
    print("⚠️  IMPORTANT: Keep backup files for 30 days")
    print("   Do not delete *.json.backup files until migration is verified")
    print()
