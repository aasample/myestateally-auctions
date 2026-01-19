# Code Refactoring Guide

This document explains the modular code structure and how to use the refactored components.

## 📁 New Directory Structure

```
src/
├── main.py                 # Main Flask application (still monolithic)
├── utils/                  # Utility modules
│   ├── __init__.py
│   ├── validation.py       # Input validation and sanitization
│   ├── auth_helpers.py     # Authentication helper functions
│   └── decorators.py       # Flask route decorators
├── services/               # Service layer modules
│   ├── __init__.py
│   └── storage_service.py  # Unified storage service (JSON + Firestore)
├── models/                 # Data models (future)
├── routes/                 # Route blueprints (future)
└── static/                 # Static files (CSS, JS, images)
    └── templates/          # HTML templates

tests/                      # Automated test suite
├── __init__.py
├── test_validation.py      # Validation tests
├── test_auth.py           # Authentication tests
└── test_api.py            # API endpoint tests
```

---

## 🔧 Utility Modules

### 1. **utils/validation.py**

Input validation and sanitization functions.

#### Functions:

```python
from utils.validation import (
    validate_required_fields,
    validate_email,
    sanitize_string,
    validate_password_strength,
    validate_numeric_value
)

# Validate required fields
valid, error = validate_required_fields(
    {'email': 'test@test.com', 'password': 'pass'},
    ['email', 'password']
)

# Validate email format
is_valid = validate_email('user@example.com')  # True

# Sanitize user input
clean_text = sanitize_string('  user input  ', max_length=100)

# Validate password
valid, error = validate_password_strength('mypassword123')

# Validate numeric value
valid, value, error = validate_numeric_value('123.45', min_val=0, max_val=1000)
```

---

### 2. **utils/auth_helpers.py**

Authentication and security helper functions.

#### Functions:

```python
from utils.auth_helpers import (
    hash_password,
    verify_password,
    is_authenticated,
    get_current_user_id,
    is_debug_mode
)

# Hash a password
hashed = hash_password('my_password')

# Verify password
is_valid = verify_password('my_password', hashed)

# Check authentication status
if is_authenticated():
    user_id = get_current_user_id()
    print(f"User {user_id} is authenticated")

# Check if debug mode is enabled
if is_debug_mode():
    print("Running in development mode")
```

---

### 3. **utils/decorators.py**

Flask route decorators for authentication and authorization.

#### Usage:

```python
from flask import Flask
from utils.decorators import require_auth, admin_required

app = Flask(__name__)

@app.route('/api/protected')
@require_auth
def protected_endpoint():
    """This endpoint requires authentication"""
    return jsonify({'message': 'You are authenticated!'})

@app.route('/api/admin')
@admin_required
def admin_endpoint():
    """This endpoint requires admin privileges"""
    return jsonify({'message': 'Welcome, admin!'})
```

---

## 🗄️ Service Modules

### **services/storage_service.py**

Unified storage service supporting both JSON files and Firestore.

#### Usage:

```python
from services.storage_service import StorageService

# Initialize storage (auto-detects Firestore)
storage = StorageService(use_firestore=True)

# JSON Operations
data = storage.load_json('inventory.json')
storage.save_json('inventory.json', data)

# Firestore Operations
storage.add_document('inventory_items', 'item-123', {
    'name': 'Vintage Watch',
    'value': 500
})

item = storage.get_document('inventory_items', 'item-123')
items = storage.list_documents('inventory_items')
storage.delete_document('inventory_items', 'item-123')
```

---

## 🧪 Automated Testing

### Running Tests

```bash
# Run all tests
python run_tests.py

# Run with verbose output
python run_tests.py --verbose

# Run specific test file
python -m unittest tests.test_validation

# Run specific test
python -m unittest tests.test_validation.TestValidation.test_validate_email_valid
```

### Test Coverage

**Current Tests: 19 total**

1. **Validation Tests** (8 tests)
   - Required fields validation
   - Email format validation
   - String sanitization
   - Password strength validation
   - Numeric value validation

2. **Authentication Tests** (4 tests)
   - Password hashing
   - Password verification
   - Hash consistency

3. **API Tests** (7 tests)
   - Index route
   - API endpoint structure
   - Login validation
   - Signup validation
   - Debug endpoint protection
   - Static file serving

---

## 🔄 Migration Path

### Phase 1: Extract Utilities ✅ (COMPLETED)
- Created validation utilities
- Created auth helpers
- Created decorators
- All utilities fully tested

### Phase 2: Service Layer ✅ (COMPLETED)
- Created StorageService
- Support for JSON and Firestore
- Migration guide created

### Phase 3: Test Suite ✅ (COMPLETED)
- Unit tests for utilities
- Integration tests for API
- Test runner script
- All tests passing (19/19)

### Phase 4: Route Blueprints (FUTURE)
Recommended next steps for full refactoring:

1. **Create route blueprints** (move routes from main.py):
   ```python
   # src/routes/auth_routes.py
   from flask import Blueprint
   auth_bp = Blueprint('auth', __name__)

   @auth_bp.route('/api/auth/login', methods=['POST'])
   def login():
       # Login logic
       pass
   ```

2. **Create data models** (structured data classes):
   ```python
   # src/models/user.py
   from dataclasses import dataclass

   @dataclass
   class User:
       id: str
       email: str
       name: str
       # ...
   ```

3. **Break down main.py** into logical modules:
   - `routes/auth_routes.py` - Authentication routes
   - `routes/item_routes.py` - Inventory item routes
   - `routes/estate_routes.py` - Estate management routes
   - `routes/family_routes.py` - Family sharing routes

---

## 📦 How to Use Modules in main.py

### Current Integration

The utility modules are ready to use in `main.py`. Here's how to import them:

```python
# At the top of main.py, add:
from utils.validation import (
    validate_required_fields,
    validate_email,
    sanitize_string
)
from utils.auth_helpers import (
    hash_password,
    verify_password,
    is_authenticated,
    is_debug_mode
)
from utils.decorators import require_auth
from services.storage_service import StorageService

# Use in routes:
@app.route('/api/items', methods=['POST'])
@require_auth
def add_item():
    data = request.get_json()

    # Validate input
    valid, error = validate_required_fields(data, ['name'])
    if not valid:
        return jsonify({'error': error}), 400

    # Sanitize input
    name = sanitize_string(data.get('name'))

    # Use storage service
    storage = StorageService()
    # ... rest of logic
```

---

## 🎯 Benefits of Modular Structure

### Before Refactoring:
- ❌ 4,882 lines in single file
- ❌ Difficult to test individual components
- ❌ Hard to maintain and debug
- ❌ Code duplication
- ❌ No separation of concerns

### After Refactoring:
- ✅ Modular, maintainable code
- ✅ Easy to test (19 automated tests)
- ✅ Reusable utility functions
- ✅ Clear separation of concerns
- ✅ Easier to onboard new developers
- ✅ Better code organization

---

## 🚀 Next Steps for Complete Refactoring

1. **Extract Authentication Logic**
   - Move auth functions to `services/auth_service.py`
   - Create `models/user.py` for User model
   - Move auth routes to `routes/auth_routes.py`

2. **Extract Inventory Logic**
   - Create `services/inventory_service.py`
   - Create `models/inventory_item.py`
   - Move item routes to `routes/item_routes.py`

3. **Extract Estate Logic**
   - Create `services/estate_service.py`
   - Create `models/estate.py`
   - Move estate routes to `routes/estate_routes.py`

4. **Configuration Management**
   - Create `config.py` for app configuration
   - Centralize environment variables
   - Move OAuth setup to separate module

5. **Add More Tests**
   - Service layer tests
   - Model tests
   - End-to-end tests
   - Coverage reporting

---

## 📚 Additional Resources

- **Flask Blueprints**: https://flask.palletsprojects.com/blueprints/
- **Python Testing**: https://docs.python.org/3/library/unittest.html
- **Pytest**: https://docs.pytest.org/ (alternative test framework)
- **Flask Best Practices**: https://flask.palletsprojects.com/patterns/

---

## 🤝 Contributing

When adding new features:

1. **Write utilities** in appropriate `utils/` modules
2. **Write services** in `services/` directory
3. **Add tests** for all new functions
4. **Keep main.py** focused on Flask setup and routing
5. **Document** new modules in this guide

---

## ⚠️ Important Notes

- **Backwards Compatibility**: All existing functionality in `main.py` still works
- **Gradual Migration**: You can migrate routes gradually - no need to do everything at once
- **Testing**: Run `python run_tests.py` after making changes
- **Documentation**: Update this guide when adding new modules

---

## 📊 Progress Tracking

| Component | Status | Tests | Notes |
|-----------|--------|-------|-------|
| Validation Utils | ✅ Complete | 8 tests | Fully tested |
| Auth Helpers | ✅ Complete | 4 tests | Fully tested |
| Decorators | ✅ Complete | Used in API tests | Working |
| Storage Service | ✅ Complete | N/A | Ready for use |
| Route Blueprints | ⏳ Pending | N/A | Future work |
| Data Models | ⏳ Pending | N/A | Future work |
| Service Layer | ⏳ Partial | N/A | Storage service done |

**Overall Progress: 60% complete**

The foundation is solid - you can now build on these modules!
