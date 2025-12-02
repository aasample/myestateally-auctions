@echo off
REM MyEstateAlly - Create Secrets in Google Cloud Secret Manager
REM This script reads your .env file and creates secrets in GCP

echo.
echo ====================================
echo  MyEstateAlly Secret Manager Setup
echo ====================================
echo.

REM Check if .env exists
if not exist ".env" (
    echo ERROR: .env file not found!
    echo Please make sure you're in the project directory.
    pause
    exit /b 1
)

echo Step 1: Setting project...
gcloud config set project estateally-ai-services
echo.

echo Step 2: Enabling Secret Manager API...
gcloud services enable secretmanager.googleapis.com
echo.

echo Step 3: Creating secrets...
echo.

REM You'll need to manually set these values
set /p SECRET_KEY="Enter your SECRET_KEY (from .env): "
set /p OPENAI_API_KEY="Enter your OPENAI_API_KEY (from .env): "
set /p GOOGLE_CLIENT_ID="Enter your GOOGLE_CLIENT_ID (from .env): "
set /p GOOGLE_CLIENT_SECRET="Enter your GOOGLE_CLIENT_SECRET (from .env): "

echo.
echo Creating SECRET_KEY...
echo %SECRET_KEY% | gcloud secrets create SECRET_KEY --data-file=- --replication-policy=automatic

echo.
echo Creating OPENAI_API_KEY...
echo %OPENAI_API_KEY% | gcloud secrets create OPENAI_API_KEY --data-file=- --replication-policy=automatic

echo.
echo Creating GOOGLE_CLIENT_ID...
echo %GOOGLE_CLIENT_ID% | gcloud secrets create GOOGLE_CLIENT_ID --data-file=- --replication-policy=automatic

echo.
echo Creating GOOGLE_CLIENT_SECRET...
echo %GOOGLE_CLIENT_SECRET% | gcloud secrets create GOOGLE_CLIENT_SECRET --data-file=- --replication-policy=automatic

echo.
echo ====================================
echo  Secrets created successfully!
echo ====================================
echo.

echo Step 4: Granting App Engine access to secrets...
echo.

REM Get project number
for /f "delims=" %%i in ('gcloud projects describe estateally-ai-services --format="value(projectNumber)"') do set PROJECT_NUMBER=%%i

echo Project Number: %PROJECT_NUMBER%
echo.

REM Grant access to each secret
gcloud secrets add-iam-policy-binding SECRET_KEY --member="serviceAccount:%PROJECT_NUMBER%-compute@developer.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding OPENAI_API_KEY --member="serviceAccount:%PROJECT_NUMBER%-compute@developer.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding GOOGLE_CLIENT_ID --member="serviceAccount:%PROJECT_NUMBER%-compute@developer.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding GOOGLE_CLIENT_SECRET --member="serviceAccount:%PROJECT_NUMBER%-compute@developer.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"

echo.
echo ====================================
echo  Setup Complete!
echo ====================================
echo.
echo Next steps:
echo 1. Update your app.yaml file
echo 2. Deploy your app with: gcloud app deploy
echo.
pause
