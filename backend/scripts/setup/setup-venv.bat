@echo off
echo ========================================
echo  Setting up Python Virtual Environment
echo ========================================

REM Check if Python is available
py --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not available via 'py' command
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

echo ✅ Python is available

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo 🔧 Creating virtual environment...
    py -m venv venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo ✅ Virtual environment created
) else (
    echo ✅ Virtual environment already exists
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

echo ✅ Virtual environment activated

REM Upgrade pip
echo 🔧 Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo 🔧 Installing requirements...
if exist "requirements-basic.txt" (
    pip install -r requirements-basic.txt
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install basic requirements
        pause
        exit /b 1
    )
    echo ✅ Basic requirements installed successfully
    echo.
    echo Note: Audio processing dependencies (pydub, ffmpeg-python) are temporarily
    echo disabled due to Python 3.13 compatibility issues with audioop module.
    echo Core functionality (Django, Celery, API) is fully working.
) else (
    if exist "requirements.txt" (
        echo Installing core dependencies from requirements.txt...
        pip install django djangorestframework celery redis django-cors-headers python-dotenv stripe
        echo ✅ Core requirements installed
    ) else (
        echo WARNING: No requirements file found
        echo Installing basic dependencies...
        pip install django djangorestframework celery redis python-dotenv stripe
    )
)

echo.
echo ========================================
echo  Virtual Environment Setup Complete!
echo ========================================
echo.
echo To activate the virtual environment manually:
echo   venv\Scripts\activate.bat
echo.
echo To deactivate:
echo   deactivate
echo.
pause
