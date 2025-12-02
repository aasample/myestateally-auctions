# Fix Data Storage - Switch to Firestore

## Problem

Your code currently uses JSON files to store data:
```python
save_storage('inventory.json', inventory_storage)  # Won't work on App Engine!
```

App Engine's filesystem is read-only, so we need to use Firestore exclusively.

---

## Solution Overview

We already have Firestore helper functions in your code, but they're not being used consistently. We need to:

1. **Remove all JSON file operations** - No more `save_storage()` or `load_storage()`
2. **Use Firestore exclusively** - All data goes to Firestore
3. **Update existing functions** - Make them use Firestore instead of JSON

---

## Step-by-Step Fixes

### Fix #1: Update Firestore Helper Functions

Your code already has these functions, but they need to be complete. Add these helper functions to your `src/main.py`:

```python
def firestore_update_inventory_item(item):
    """Update an existing item in Firestore"""
    client = get_firestore_client()
    if client is None:
        return False
    try:
        client.collection('inventory').document(item['id']).set(item)
        return True
    except Exception as e:
        logger.error(f"Failed to update item in Firestore: {e}")
        return False

def firestore_delete_inventory_item(item_id):
    """Delete an item from Firestore"""
    client = get_firestore_client()
    if client is None:
        return False
    try:
        client.collection('inventory').document(item_id).delete()
        return True
    except Exception as e:
        logger.error(f"Failed to delete item from Firestore: {e}")
        return False

def firestore_get_user_estates(user_id):
    """Get all estates for a user from Firestore"""
    client = get_firestore_client()
    if client is None:
        return []
    try:
        docs = client.collection('estates').where('owner_id', '==', user_id).stream()
        estates = []
        for doc in docs:
            estate = doc.to_dict()
            estate['id'] = doc.id
            estates.append(estate)
        # Also get estates where user is a member
        member_docs = client.collection('estates').where(f'members.{user_id}', '!=', None).stream()
        for doc in member_docs:
            estate = doc.to_dict()
            estate['id'] = doc.id
            if estate not in estates:
                estates.append(estate)
        return estates
    except Exception as e:
        logger.error(f"Failed to get user estates: {e}")
        return []

def firestore_save_estate(estate_id, estate_data):
    """Save estate data to Firestore"""
    client = get_firestore_client()
    if client is None:
        return False
    try:
        client.collection('estates').document(estate_id).set(estate_data)
        return True
    except Exception as e:
        logger.error(f"Failed to save estate: {e}")
        return False

def firestore_save_family_data(estate_id, family_data):
    """Save family sharing data to Firestore"""
    client = get_firestore_client()
    if client is None:
        return False
    try:
        client.collection('family_sharing').document(estate_id).set(family_data)
        return True
    except Exception as e:
        logger.error(f"Failed to save family data: {e}")
        return False

def firestore_get_family_data(estate_id):
    """Get family sharing data from Firestore"""
    client = get_firestore_client()
    if client is None:
        return None
    try:
        doc = client.collection('family_sharing').document(estate_id).get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        logger.error(f"Failed to get family data: {e}")
        return None
```

### Fix #2: Update `add_item()` Function

Find this function in your code (around line 600) and replace it:

**OLD CODE:**
```python
@app.route('/api/items', methods=['POST'])
def add_item():
    # ... existing code ...

    # Prefer Firestore; fall back to JSON file
    if not firestore_add_inventory_item(item):
        inventory_storage[item_id] = item
        save_storage('inventory.json', inventory_storage)  # ❌ Remove this
```

**NEW CODE:**
```python
@app.route('/api/items', methods=['POST'])
@require_auth  # Add authentication
def add_item():
    # ... existing code ...

    # Use Firestore exclusively
    if firestore_add_inventory_item(item):
        # Also update in-memory cache
        inventory_storage[item_id] = item
        return jsonify({
            'success': True,
            'message': 'Item added successfully',
            'item': item
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Failed to save item to database'
        }), 500
```

### Fix #3: Update `update_item()` Function

**Find and replace:**

```python
@app.route('/api/items/<item_id>', methods=['PUT'])
@require_auth  # Add authentication
def update_item(item_id):
    try:
        data = request.get_json()

        # Get item from Firestore
        client = get_firestore_client()
        if not client:
            return jsonify({'success': False, 'error': 'Database unavailable'}), 500

        doc = client.collection('inventory').document(item_id).get()
        if not doc.exists:
            return jsonify({'success': False, 'error': 'Item not found'}), 404

        item = doc.to_dict()

        # Update fields
        item['name'] = data.get('name', item['name'])
        item['category'] = data.get('category', item['category'])
        item['description'] = data.get('description', item['description'])
        item['estimatedValue'] = float(data.get('estimatedValue', item['estimatedValue']))
        item['forSale'] = data.get('forSale', item['forSale'])
        item['assignedTo'] = data.get('assignedTo', item['assignedTo'])
        item['lastModified'] = datetime.now().isoformat()

        # Save to Firestore
        if firestore_update_inventory_item(item):
            inventory_storage[item_id] = item  # Update cache
            return jsonify({'success': True, 'message': 'Item updated', 'item': item})
        else:
            return jsonify({'success': False, 'error': 'Failed to update item'}), 500

    except Exception as e:
        logger.error(f"Error updating item: {e}")
        return jsonify({'success': False, 'error': 'Failed to update item'}), 500
```

### Fix #4: Update `delete_item()` Function

```python
@app.route('/api/items/<item_id>', methods=['DELETE'])
@require_auth  # Add authentication
def delete_item(item_id):
    try:
        # Delete from Firestore
        if firestore_delete_inventory_item(item_id):
            # Remove from cache
            if item_id in inventory_storage:
                del inventory_storage[item_id]
            return jsonify({'success': True, 'message': 'Item deleted'})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete item'}), 500

    except Exception as e:
        logger.error(f"Error deleting item: {e}")
        return jsonify({'success': False, 'error': 'Failed to delete item'}), 500
```

### Fix #5: Remove All `save_storage()` Calls

Search your code for these lines and remove them:
```python
save_storage('inventory.json', inventory_storage)  # DELETE
save_storage('users.json', user_storage)  # DELETE
save_storage('family.json', family_storage)  # DELETE
save_storage('estates.json', estate_storage)  # DELETE
```

Replace with Firestore calls as shown above.

### Fix #6: Update Initialization Code

At the top of your file, remove/comment out JSON loading:

```python
# OLD CODE - Remove or comment out:
# inventory_storage = load_storage('inventory.json')
# user_storage = load_storage('users.json')
# family_storage = load_storage('family.json')

# NEW CODE - Load from Firestore on startup:
inventory_storage = {}
user_storage = {}
family_storage = {'estates': {}, 'share_links': {}}

# Load initial data from Firestore
try:
    items = firestore_list_inventory_items()
    if items:
        for item in items:
            inventory_storage[item['id']] = item
        logger.info(f"Loaded {len(items)} items from Firestore")
except Exception as e:
    logger.warning(f"Could not load initial inventory: {e}")
```

---

## Testing Locally

After making these changes:

1. Make sure Firestore is enabled in your project
2. Test creating, updating, and deleting items
3. Check that data persists (reload the page)

---

## Verification Checklist

- [ ] All `save_storage()` calls removed
- [ ] All `load_storage()` calls removed
- [ ] All item operations use Firestore
- [ ] `@require_auth` added to endpoints
- [ ] Tested locally
- [ ] Ready to deploy

---

This is a significant change, so take your time and test thoroughly!
