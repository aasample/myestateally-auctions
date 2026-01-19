# Migration Guide: JSON Storage to Firestore

This guide will help you migrate your MyEstateAlly data from JSON file storage to Google Cloud Firestore for production use.

## Why Migrate to Firestore?

**Current JSON Storage Limitations:**
- ❌ No concurrent access support (race conditions possible)
- ❌ Not scalable for multiple users
- ❌ Single point of failure
- ❌ Manual backup required
- ❌ Limited query capabilities

**Firestore Benefits:**
- ✅ Real-time synchronization
- ✅ Automatic scaling
- ✅ Built-in redundancy and backups
- ✅ Concurrent access support
- ✅ Advanced querying
- ✅ Mobile/web SDK support

---

## Prerequisites

1. **Google Cloud Project**: Active project with billing enabled
2. **Firestore Database**: Firestore enabled in your project
3. **Service Account**: Credentials for local development
4. **Dependencies**: All packages from requirements.txt installed

---

## Step 1: Enable Firestore in Google Cloud

### Via Console:
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Select your project
3. Navigate to **Firestore** > **Database**
4. Click **Create Database**
5. Select **Native Mode** (recommended)
6. Choose a location (e.g., us-central1)
7. Click **Create**

### Via CLI:
```bash
gcloud firestore databases create --location=us-central1
```

---

## Step 2: Set Up Service Account (For Local Development)

### Create Service Account:
```bash
gcloud iam service-accounts create myestateally-dev \
    --display-name="MyEstateAlly Development"
```

### Grant Firestore Permissions:
```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:myestateally-dev@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/datastore.user"
```

### Create and Download Key:
```bash
gcloud iam service-accounts keys create firestore-key.json \
    --iam-account=myestateally-dev@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### Set Environment Variable:
```bash
# Windows
set GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\firestore-key.json

# Linux/Mac
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/firestore-key.json
```

---

## Step 3: Update Environment Configuration

Add to your `.env` file:
```env
# Google Cloud Project
GOOGLE_CLOUD_PROJECT=your-project-id

# For local development only (not needed on App Engine)
GOOGLE_APPLICATION_CREDENTIALS=./firestore-key.json

# Enable Firestore
USE_FIRESTORE=true
```

---

## Step 4: Firestore Collections Structure

Your data will be organized in these collections:

### **Collection: `users`**
- Document ID: user_id (UUID)
- Fields:
  - email (string)
  - password_hash (string)
  - name (string)
  - provider (string): 'email', 'google', 'facebook'
  - created_at (timestamp)
  - last_login (timestamp)
  - mfa_enabled (boolean)
  - mfa_secret (string, optional)

### **Collection: `estates`**
- Document ID: estate_id (UUID)
- Fields:
  - name (string)
  - owner_id (string): reference to user
  - created_at (timestamp)
  - last_modified (timestamp)
  - shared_with (array of strings): user IDs

### **Collection: `inventory_items`**
- Document ID: item_id (UUID)
- Fields:
  - estate_id (string): reference to estate
  - name (string)
  - category (string)
  - description (string)
  - estimated_value (number)
  - for_sale (boolean)
  - assigned_to (string)
  - photo (string): Cloud Storage URL
  - date_added (timestamp)
  - last_modified (timestamp)

---

## Step 5: Migration Script

Create `migrate_to_firestore.py`:

```python
#!/usr/bin/env python3
"""
Migration script to move data from JSON files to Firestore
"""
import json
import os
from google.cloud import firestore
from datetime import datetime

def migrate_data():
    """Migrate all data from JSON to Firestore"""
    print("Starting migration to Firestore...")

    # Initialize Firestore client
    db = firestore.Client()

    # Migrate Users
    print("\n1. Migrating users...")
    if os.path.exists('auth.json'):
        with open('auth.json', 'r') as f:
            auth_data = json.load(f)
            users = auth_data.get('users', {})

        for user_id, user_data in users.items():
            db.collection('users').document(user_id).set(user_data)
            print(f"   ✓ Migrated user: {user_data.get('email')}")

        print(f"   Migrated {len(users)} users")
    else:
        print("   No auth.json found, skipping users")

    # Migrate Estates
    print("\n2. Migrating estates...")
    if os.path.exists('estates.json'):
        with open('estates.json', 'r') as f:
            estates = json.load(f)

        for estate_id, estate_data in estates.items():
            db.collection('estates').document(estate_id).set(estate_data)
            print(f"   ✓ Migrated estate: {estate_data.get('name')}")

        print(f"   Migrated {len(estates)} estates")
    else:
        print("   No estates.json found, skipping estates")

    # Migrate Inventory Items
    print("\n3. Migrating inventory items...")
    if os.path.exists('inventory.json'):
        with open('inventory.json', 'r') as f:
            inventory = json.load(f)

        for item_id, item_data in inventory.items():
            db.collection('inventory_items').document(item_id).set(item_data)
            print(f"   ✓ Migrated item: {item_data.get('name')}")

        print(f"   Migrated {len(inventory)} items")
    else:
        print("   No inventory.json found, skipping items")

    print("\n✅ Migration completed successfully!")
    print("\nNext steps:")
    print("1. Verify data in Firestore Console")
    print("2. Test your application")
    print("3. Create backups of JSON files")
    print("4. Update app.yaml to use Firestore")

if __name__ == '__main__':
    try:
        migrate_data()
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
```

### Run Migration:
```bash
python migrate_to_firestore.py
```

---

## Step 6: Verify Migration

### Check Firestore Console:
1. Go to [Firestore Console](https://console.cloud.google.com/firestore)
2. Verify collections exist: `users`, `estates`, `inventory_items`
3. Check document counts match your JSON files

### Test Locally:
```bash
# Set environment to use Firestore
export USE_FIRESTORE=true

# Start application
python run_local.py

# Test functionality
# - Login/signup
# - Create items
# - List items
```

---

## Step 7: Update Production Configuration

Update `app.yaml.production`:

```yaml
runtime: python311

env_variables:
  FLASK_ENV: production
  USE_FIRESTORE: "true"
  GOOGLE_CLOUD_PROJECT: "your-project-id"
  # ... other variables
```

**Note**: On App Engine, authentication is automatic - no service account key needed!

---

## Step 8: Deploy to Production

```bash
# Test locally first
python run_local.py

# Deploy when ready
gcloud app deploy app.yaml.production

# Verify deployment
gcloud app browse
```

---

## Step 9: Create Backups

### Automatic Firestore Backups:

```bash
# Schedule daily backups
gcloud firestore backups schedules create \
    --database='(default)' \
    --recurrence=daily \
    --retention=7d
```

### Manual Backup:

```bash
# Export to Cloud Storage
gcloud firestore export gs://YOUR_BUCKET_NAME/firestore-backup
```

---

## Step 10: Performance Optimization

### Create Indexes (if needed):

```bash
# Create firestore.indexes.json
cat > firestore.indexes.json << EOF
{
  "indexes": [
    {
      "collectionGroup": "inventory_items",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "estate_id", "order": "ASCENDING" },
        { "fieldPath": "date_added", "order": "DESCENDING" }
      ]
    }
  ]
}
EOF

# Deploy indexes
gcloud firestore indexes create --file=firestore.indexes.json
```

---

## Rollback Plan

If you need to rollback to JSON storage:

1. **Stop Application**:
   ```bash
   # Stop App Engine version
   gcloud app versions stop VERSION_ID
   ```

2. **Restore JSON Files**:
   ```bash
   # Copy from backup
   cp backup/inventory.json ./
   cp backup/auth.json ./
   cp backup/estates.json ./
   ```

3. **Update Environment**:
   ```env
   USE_FIRESTORE=false
   ```

4. **Redeploy**:
   ```bash
   gcloud app deploy
   ```

---

## Troubleshooting

### Error: "Permission Denied"
- **Solution**: Check IAM roles and service account permissions
  ```bash
  gcloud projects get-iam-policy YOUR_PROJECT_ID
  ```

### Error: "Firestore not enabled"
- **Solution**: Enable Firestore API
  ```bash
  gcloud services enable firestore.googleapis.com
  ```

### Error: "Quota exceeded"
- **Solution**: Check Firestore quotas in console
- Consider upgrading to Blaze (pay-as-you-go) plan

### Performance Issues
- **Solution**: Check indexes
  ```bash
  gcloud firestore indexes list
  ```
- Review query patterns in logs

---

## Cost Estimation

### Firestore Pricing (as of 2024):

**Free Tier (Daily):**
- 50,000 document reads
- 20,000 document writes
- 20,000 document deletes
- 1 GB storage

**Beyond Free Tier:**
- Reads: $0.06 per 100K documents
- Writes: $0.18 per 100K documents
- Deletes: $0.02 per 100K documents
- Storage: $0.18/GB/month

**Example Cost** (1000 active users):
- ~$10-30/month depending on usage patterns

---

## Additional Resources

- [Firestore Documentation](https://cloud.google.com/firestore/docs)
- [Python Client Library](https://cloud.google.com/python/docs/reference/firestore/latest)
- [Best Practices](https://cloud.google.com/firestore/docs/best-practices)
- [Security Rules](https://cloud.google.com/firestore/docs/security/get-started)

---

## Support

If you encounter issues:
1. Check application logs: `gcloud app logs tail`
2. Review Firestore logs in Cloud Console
3. Verify service account permissions
4. Test locally with `GOOGLE_APPLICATION_CREDENTIALS`

**Migration completed successfully? Don't forget to:**
- ✅ Backup JSON files to Cloud Storage
- ✅ Update documentation
- ✅ Monitor Firestore usage
- ✅ Set up alerting for errors
