# 🔐 Secret Management Setup Guide

This guide shows you how to securely manage your API keys and secrets for MyEstateAlly.

## ⚠️ IMPORTANT RULES

1. **NEVER** commit `.env` file to git
2. **NEVER** put secrets in `app.yaml`
3. **ALWAYS** use Secret Manager for production
4. **ALWAYS** rotate keys if they're exposed

---

## 🏠 Local Development Setup

### Step 1: Create .env File

Copy the example file:
```bash
copy .env.example .env
```

### Step 2: Fill in Your Secrets

Edit `.env` with your actual values:

```bash
# Generate a strong SECRET_KEY first:
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Then fill in .env:
SECRET_KEY=<paste the generated key>
OPENAI_API_KEY=sk-proj-<your new OpenAI key>
GOOGLE_CLIENT_ID=<your Google OAuth client ID>
GOOGLE_CLIENT_SECRET=<your new Google OAuth secret>
```

### Step 3: Verify It's Ignored by Git

```bash
git status
```

The `.env` file should **NOT** appear in the list. If it does, check your `.gitignore` file.

### Step 4: Test Locally

```bash
python main.py
```

Visit http://localhost:8080 and verify everything works.

---

## ☁️ Google Cloud Production Setup

### Step 1: Enable Secret Manager

```bash
gcloud services enable secretmanager.googleapis.com
```

### Step 2: Create Secrets

```bash
# Create SECRET_KEY
echo -n "your-32-char-secret-key" | gcloud secrets create SECRET_KEY --data-file=-

# Create OPENAI_API_KEY
echo -n "sk-proj-your-key" | gcloud secrets create OPENAI_API_KEY --data-file=-

# Create GOOGLE_CLIENT_SECRET
echo -n "your-google-secret" | gcloud secrets create GOOGLE_CLIENT_SECRET --data-file=-

# Create GOOGLE_CLIENT_ID (not really secret but for consistency)
echo -n "your-client-id.apps.googleusercontent.com" | gcloud secrets create GOOGLE_CLIENT_ID --data-file=-
```

### Step 3: Grant App Engine Access

```bash
# Get your project number
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format="value(projectNumber)")

# Grant access to Secret Manager
gcloud secrets add-iam-policy-binding SECRET_KEY \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding OPENAI_API_KEY \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding GOOGLE_CLIENT_SECRET \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding GOOGLE_CLIENT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Step 4: Update app.yaml

Edit `app.yaml` and add secret references:

```yaml
env_variables:
  SECRET_KEY: "projects/YOUR_PROJECT_ID/secrets/SECRET_KEY/versions/latest"
  OPENAI_API_KEY: "projects/YOUR_PROJECT_ID/secrets/OPENAI_API_KEY/versions/latest"
  GOOGLE_CLIENT_ID: "projects/YOUR_PROJECT_ID/secrets/GOOGLE_CLIENT_ID/versions/latest"
  GOOGLE_CLIENT_SECRET: "projects/YOUR_PROJECT_ID/secrets/GOOGLE_CLIENT_SECRET/versions/latest"
```

Replace `YOUR_PROJECT_ID` with your actual Google Cloud project ID.

### Step 5: Deploy

```bash
gcloud app deploy
```

---

## 🔄 Rotating Secrets

If a secret is compromised:

### For Local Development:
1. Generate new key/secret from provider
2. Update `.env` file
3. Restart your local server

### For Production:
1. Generate new key/secret from provider
2. Update the secret in Secret Manager:
   ```bash
   echo -n "new-secret-value" | gcloud secrets versions add SECRET_NAME --data-file=-
   ```
3. Redeploy your app:
   ```bash
   gcloud app deploy
   ```

---

## 📋 Checklist

Before committing to GitHub:
- [ ] `.env` file is in `.gitignore`
- [ ] No secrets in `app.yaml`
- [ ] No secrets in any Python files
- [ ] Run `git status` - `.env` should NOT appear

Before deploying to production:
- [ ] All secrets created in Secret Manager
- [ ] App Engine has access to secrets
- [ ] `app.yaml` references secrets correctly
- [ ] Test deployment with `gcloud app deploy`

---

## 🆘 Help

If you accidentally commit secrets:
1. Immediately rotate ALL exposed keys
2. Remove from git history:
   ```bash
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch .env" \
     --prune-empty --tag-name-filter cat -- --all
   ```
3. Force push (if safe to do so)
4. Consider repository as compromised - may need to delete and recreate

---

## 📚 Resources

- [Google Cloud Secret Manager](https://cloud.google.com/secret-manager/docs)
- [OpenAI API Keys](https://platform.openai.com/api-keys)
- [Google OAuth Setup](https://console.cloud.google.com/apis/credentials)
