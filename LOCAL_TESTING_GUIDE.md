# Local Testing Guide for MyEstateAlly

This guide will help you test the application locally before deploying to Google App Engine.

## Prerequisites

1. **Python 3.11** installed (check with `python --version`)
2. **Virtual environment** (recommended) - Python's `venv` module

## Step 1: Set Up Virtual Environment

```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1
# Or on Windows CMD: venv\Scripts\activate.bat
# Or on Mac/Linux: source venv/bin/activate
```

## Step 2: Install Dependencies

```powershell
pip install -r requirements.txt
```

## Step 3: Set Up Environment Variables

Create a `.env` file in the project root (or set environment variables):

```env
SECRET_KEY=myestateally-dev-testing-key-2024-local
OPENAI_API_KEY=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
GOOGLE_CLIENT_ID=534529839786-jn1008urf304qnugpg5goohgpqkgk76k.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=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
GOOGLE_REDIRECT_URI=http://localhost:8080/auth/google/callback
FACEBOOK_CLIENT_ID=
FACEBOOK_CLIENT_SECRET=
FACEBOOK_REDIRECT_URI=http://localhost:8080/auth/facebook/callback

# Email configuration (optional for local testing)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=noreply@myestateally.com
```

## Step 4: Run the Application Locally

```powershell
# Navigate to src directory
cd src

# Run the Flask app
python main.py
```

The app will start on **http://localhost:8080**

## Step 5: Test Key Features

### 1. **Basic Access**
- Open http://localhost:8080 in your browser
- Verify the page loads correctly
- Check that dark mode works (if your system is in dark mode)

### 2. **Authentication**
- Click "Sign Up" button
- Create a test account (email/password)
- Verify login works
- Test logout

### 3. **Estate Management** ⭐ NEW
- After login, click the "+" button next to estate selector
- Create a test estate (e.g., "Test Estate 1")
- Verify estate appears in the dropdown
- Create a second estate and switch between them

### 4. **Inventory Management**
- Go to Inventory tab
- Add a new item manually
- Verify item appears in the list
- Edit an item
- Delete an item
- Switch estates and verify items are separated

### 5. **AI Pricing**
- Go to AI Pricing tab
- Select an item from inventory
- Click "Lookup Pricing"
- Verify pricing results appear with links

### 6. **Family Sharing** ⭐ UPDATED
- Go to Family tab
- Invite a family member (use a real email or test email)
- Verify member appears in the list
- Generate a share link
- Copy the share link
- Open share link in incognito/private window
- Test desire level selection (1-5)
- Verify desires appear in owner's view

### 7. **Estate Settlement**
- Go to Estate Settlement tab
- Add a new task
- Update task status
- Dispose an item (sold/donated/discarded)
- Check disposal summary

### 8. **Reports**
- Test assignment report generation
- Verify PDF downloads (if implemented)

## Step 6: Check Console for Errors

Watch the terminal/console where Flask is running for:
- ✅ Success messages
- ❌ Error messages
- Warning messages

## Step 7: Test Database/Storage

Check that data persists:
- Create an item → restart server → verify item still exists
- Switch estates → verify data isolation
- Create family member → verify persistence

## Quick Test Script

You can also create a simple test script. Save this as `test_local.py`:

```python
import requests
import json

BASE_URL = "http://localhost:8080"

def test_endpoints():
    """Quick API endpoint tests"""
    
    print("Testing MyEstateAlly Local Server...")
    print(f"Server: {BASE_URL}\n")
    
    # Test 1: Homepage
    print("1. Testing homepage...")
    try:
        r = requests.get(BASE_URL)
        assert r.status_code == 200
        print("   ✅ Homepage accessible")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 2: Auth status (should be unauthenticated)
    print("2. Testing auth status...")
    try:
        r = requests.get(f"{BASE_URL}/api/auth/status")
        data = r.json()
        assert 'authenticated' in data
        print(f"   ✅ Auth status: {data.get('authenticated', False)}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 3: Inventory (should require estate)
    print("3. Testing inventory endpoint...")
    try:
        r = requests.get(f"{BASE_URL}/api/items")
        data = r.json()
        print(f"   ✅ Inventory endpoint: {data.get('message', 'OK')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n✅ Basic endpoint tests complete!")
    print("   (Full testing requires authentication and estate selection)")

if __name__ == "__main__":
    test_endpoints()
```

Run with: `python test_local.py` (requires `requests` package)

## Common Issues & Solutions

### Issue: Port 8080 already in use
**Solution:** Change port in `src/main.py`:
```python
app.run(host='0.0.0.0', port=5000, debug=True)  # Use port 5000 instead
```

### Issue: Module not found errors
**Solution:** Make sure virtual environment is activated and dependencies installed:
```powershell
pip install -r requirements.txt
```

### Issue: Session/Secret Key errors
**Solution:** Make sure `SECRET_KEY` is set in `.env` file or environment variables

### Issue: File permission errors (Windows)
**Solution:** Run PowerShell as Administrator, or ensure write permissions to temp directory

## Testing Checklist

Before deploying, verify:

- [ ] App starts without errors
- [ ] Can create and login with account
- [ ] Can create multiple estates
- [ ] Can switch between estates
- [ ] Inventory items are estate-specific
- [ ] Family sharing works per estate
- [ ] Estate timeline works
- [ ] Item disposal tracking works
- [ ] No console errors during normal use
- [ ] Dark mode works correctly
- [ ] Mobile upload QR code generates
- [ ] All tabs/sections load correctly

## Next Steps

Once local testing is successful:
1. Review any errors or warnings
2. Fix any issues found
3. Deploy to Google App Engine: `gcloud app deploy --quiet`




