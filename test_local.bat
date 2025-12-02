@echo off
REM Local Testing Script for MyEstateAlly (Windows)
echo ================================================
echo MyEstateAlly - Local Testing
echo ================================================
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
echo.

REM Install/update dependencies
echo Installing dependencies...
pip install -r requirements.txt
echo.

REM Check if .env file exists
if not exist ".env" (
    echo Warning: .env file not found.
    echo Creating a sample .env file...
    (
        echo SECRET_KEY=myestateally-dev-testing-key-2024-local
        echo OPENAI_API_KEY=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
        echo GOOGLE_CLIENT_ID=534529839786-jn1008urf304qnugpg5goohgpqkgk76k.apps.googleusercontent.com
        echo GOOGLE_CLIENT_SECRET=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
        echo GOOGLE_REDIRECT_URI=http://localhost:8080/auth/google/callback
    ) > .env
    echo Sample .env file created. Please edit it with your actual values.
    echo.
)

echo Starting Flask development server...
echo Server will be available at: http://localhost:8080
echo Press Ctrl+C to stop the server
echo.
echo ================================================
echo.

REM Run the local server
python run_local.py




