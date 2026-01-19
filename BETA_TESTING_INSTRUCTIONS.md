# Beta Testing Setup - Quick Start Guide

## ✅ What's Been Done

Your application now has:

1. **Firestore Integration** - Data persists across deployments (no more inventory disappearing!)
2. **Beta Account System** - Free accounts for family members
3. **Account Types** - Users can be: `beta`, `free`, or `premium`
4. **Grandfathering** - Beta testers get free lifetime access

## 🎯 Two Ways to Create Beta Accounts

### Option 1: Beta Code System (Self-Signup)

Share this beta code with your family: **ESTATEALLY2026**

They can sign up at https://estateally-ai-services.ue.r.appspot.com and enter the beta code during signup.

**How it works:**
- Users enter the beta code during signup
- They get `account_type: 'beta'` automatically
- They're marked as `grandfathered: true` (free forever)

### Option 2: Manual Account Creation

Create accounts for family members using the script:

```bash
python create_beta_account.py
```

The script will:
- Ask for email and name
- Generate a temporary password
- Create the account in Firestore
- Print a welcome email template to send them

## 📝 User Fields

Every user now has these fields:

```python
{
    'id': 'user_xxx',
    'email': 'user@example.com',
    'name': 'User Name',
    'account_type': 'beta',  # 'beta', 'free', or 'premium'
    'grandfathered': True,   # Beta testers = true
    'stripe_customer_id': None,  # For future Stripe integration
    'created_at': '2026-01-19T...',
    'provider': 'email'
}
```

## 🚀 Deployment

Before deploying, make sure:

1. **app.yaml is configured** (already done ✅)
   - `USE_FIRESTORE: "true"` - Data persists
   - `BETA_CODE: "ESTATEALLY2026"` - Beta signup code
   - `REQUIRE_AUTH_FOR_ALL: "false"` - Optional auth

2. **Deploy the application:**
   ```bash
   gcloud app deploy
   ```

3. **Test that Firestore is working:**
   - Sign up with beta code
   - Add an inventory item
   - Deploy again (data should persist)

## 🔒 Data Persistence

**Before (JSON files):**
- ❌ Data lost on every deployment
- ❌ Not shared across instances
- ❌ Ephemeral App Engine disk

**After (Firestore):**
- ✅ Data persists forever
- ✅ Real-time across instances
- ✅ Automatic backups
- ✅ Free tier: 50K reads/day, 20K writes/day

## 💡 Future: Adding Stripe Payments

When ready to monetize (after beta testing):

1. Install Stripe: `pip install stripe`
2. Add to requirements.txt
3. Create pricing tiers:
   - **Beta** (grandfathered): Free forever
   - **Free**: Limited features
   - **Premium** ($9.99/month): All features

4. Beta testers keep their `account_type: 'beta'` and `grandfathered: true`
5. They NEVER pay, even after you launch

## 📧 Beta Tester Welcome Email Template

```
Subject: You're invited to beta test MyEstateAlly! 🎉

Hi [Name],

You're invited to be one of the first people to test MyEstateAlly!

**Your Beta Access:**
- URL: https://estateally-ai-services.ue.r.appspot.com
- Beta Code: ESTATEALLY2026 (for self-signup)
OR
- Email: [email]
- Password: [temp_password]

**What to Test:**
- Create inventory items
- Try AI pricing
- Use family sharing
- Mobile upload

**We Need Your Feedback:**
- What do you love?
- What's confusing?
- Any bugs?

As a thank you:
✅ Free during beta
✅ Free lifetime access after launch!

Thanks!
- Alicia
```

## 🎯 Testing Checklist

Before inviting family:

- [ ] Deploy with Firestore enabled
- [ ] Create a test beta account
- [ ] Add inventory items
- [ ] Redeploy to verify data persists
- [ ] Test signup with beta code
- [ ] Verify `account_type: 'beta'` is set correctly

## ❓ Troubleshooting

**Q: Data is still disappearing**
A: Check logs - make sure `USE_FIRESTORE: "true"` and you see "Firestore storage enabled" in logs

**Q: Beta code not working**
A: Check app.yaml has `BETA_CODE: "ESTATEALLY2026"` and redeploy

**Q: Can't create accounts**
A: Run `python create_beta_account.py` - requires Google Cloud credentials

**Q: How do I check Firestore?**
A: Visit https://console.cloud.google.com/firestore and select your project

## 📊 Monitoring Beta Usage

Check Firestore console to see:
- Number of users created
- Inventory items added
- Account types distribution

You can query Firestore:
```python
# Count beta users
beta_users = db.collection('users').where('account_type', '==', 'beta').stream()
print(f"Beta testers: {len(list(beta_users))}")
```

---

**Ready to deploy!** Run `gcloud app deploy` and start inviting family members to test.
