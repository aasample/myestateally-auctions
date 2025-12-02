# 🔐 Google Cloud Secret Manager Setup Guide

This guide will help you securely store your API keys in Google Cloud Secret Manager.

---

## ✅ Prerequisites

Before starting, make sure you have:
- [ ] Google Cloud CLI installed (`gcloud --version` works)
- [ ] Logged in to Google Cloud (`gcloud auth login`)
- [ ] Your `.env` file with all secrets filled in

---

## 🚀 Quick Setup (Using Script)

### Option 1: Use the Automated Script (Easiest)

1. Open Command Prompt in your project folder:
   ```bash
   cd "G:\My Drive\AI\Ai business\Deployment 61\myestateally-complete"
   ```

2. Copy the `setup-secrets.bat` file to your project:
   ```bash
   copy setup-secrets.bat "G:\My Drive\AI\Ai business\Deployment 61\myestateally-complete\"
   ```

3. Run the script:
   ```bash
   setup-secrets.bat
   ```

4. When prompted, copy and paste each value from your `.env` file

---

## 🔧 Manual Setup (If Script Doesn't Work)

### Step 1: Enable Secret Manager API

```bash
gcloud services enable secretmanager.googleapis.com
```

### Step 2: Create Each Secret

You'll need to create 4 secrets. For each one, replace `YOUR_VALUE` with the actual value from your `.env` file.

#### Create SECRET_KEY:
```bash
echo YOUR_SECRET_KEY | gcloud secrets create SECRET_KEY --data-file=- --replication-policy=automatic
```

#### Create OPENAI_API_KEY:
```bash
echo sk-proj-YOUR_KEY | gcloud secrets create OPENAI_API_KEY --data-file=- --replication-policy=automatic
```

#### Create GOOGLE_CLIENT_ID:
```bash
echo YOUR_CLIENT_ID.apps.googleusercontent.com | gcloud secrets create GOOGLE_CLIENT_ID --data-file=- --replication-policy=automatic
```

#### Create GOOGLE_CLIENT_SECRET:
```bash
echo GOCSPX-YOUR_SECRET | gcloud secrets create GOOGLE_CLIENT_SECRET --data-file=- --replication-policy=automatic
```

### Step 3: Get Your Project Number

```bash
gcloud projects describe estateally-ai-services --format="value(projectNumber)"
```

Copy the number you see (like: 123456789012)

### Step 4: Grant App Engine Access

Replace `PROJECT_NUMBER` with the number from Step 3:

```bash
gcloud secrets add-iam-policy-binding SECRET_KEY ^
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" ^
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding OPENAI_API_KEY ^
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" ^
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding GOOGLE_CLIENT_ID ^
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" ^
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding GOOGLE_CLIENT_SECRET ^
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" ^
  --role="roles/secretmanager.secretAccessor"
```

---

## ✅ Verify Your Secrets

List all secrets to make sure they were created:

```bash
gcloud secrets list
```

You should see:
```
NAME                  CREATED              REPLICATION_POLICY  LOCATIONS
GOOGLE_CLIENT_ID      2025-12-02T...       automatic           -
GOOGLE_CLIENT_SECRET  2025-12-02T...       automatic           -
OPENAI_API_KEY        2025-12-02T...       automatic           -
SECRET_KEY            2025-12-02T...       automatic           -
```

---

## 📝 Update app.yaml

Now that your secrets are in Secret Manager, update your `app.yaml`:

```yaml
runtime: python311

service: default

instance_class: F2

automatic_scaling:
  min_instances: 0
  max_instances: 10
  target_cpu_utilization: 0.65

env_variables:
  FLASK_ENV: production
  FLASK_DEBUG: "false"

  # Load secrets from Secret Manager
  SECRET_KEY: "projects/estateally-ai-services/secrets/SECRET_KEY/versions/latest"
  OPENAI_API_KEY: "projects/estateally-ai-services/secrets/OPENAI_API_KEY/versions/latest"
  GOOGLE_CLIENT_ID: "projects/estateally-ai-services/secrets/GOOGLE_CLIENT_ID/versions/latest"
  GOOGLE_CLIENT_SECRET: "projects/estateally-ai-services/secrets/GOOGLE_CLIENT_SECRET/versions/latest"

  # Other non-secret configs
  GOOGLE_REDIRECT_URI: "https://estateally-ai-services.ue.r.appspot.com/auth/google/callback"
  MAIL_SERVER: "smtp.gmail.com"
  MAIL_PORT: "587"
  MAIL_USE_TLS: "true"
  MAIL_DEFAULT_SENDER: "noreply@myestateally.com"

handlers:
- url: /static
  static_dir: src/static
  secure: always
  expiration: 1d

- url: /.*
  script: auto
  secure: always
```

---

## 🚀 Deploy Your App

Now you can safely deploy:

```bash
gcloud app deploy
```

---

## 🔄 Updating a Secret

If you need to change a secret later:

```bash
echo NEW_VALUE | gcloud secrets versions add SECRET_NAME --data-file=-
```

Then redeploy your app:

```bash
gcloud app deploy
```

---

## 🆘 Troubleshooting

### "Secret already exists"
If you see this error, the secret is already created. To update it:
```bash
echo NEW_VALUE | gcloud secrets versions add SECRET_NAME --data-file=-
```

### "Permission denied"
Make sure you have the right permissions:
```bash
gcloud projects get-iam-policy estateally-ai-services
```

### "Secret not found" when deploying
Make sure you granted App Engine access (Step 4 above)

---

## ✅ Checklist

Before deploying:
- [ ] All 4 secrets created in Secret Manager
- [ ] App Engine service account has access to secrets
- [ ] app.yaml updated with secret references
- [ ] Tested locally with `.env` file
- [ ] Ready to deploy with `gcloud app deploy`

---

**Need help? Let me know which step you're on!**
