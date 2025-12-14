@echo off
echo ========================================
echo  Audio Duplicate Detection Dev Setup
echo  (With Virtual Environment)
echo ========================================

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run setup-venv.bat first to create the virtual environment
    pause
    exit /b 1
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

echo ✅ Virtual environment activated
echo Current Python: 
python --version
echo Current pip packages location:
where python

echo.
echo 🔧 Checking Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not installed or not running
    echo Please install Docker Desktop and make sure it's running
    pause
    exit /b 1
)

echo ✅ Docker is available

echo.
echo 🚀 Starting Docker containers (Redis)...
docker-compose up -d
if %errorlevel% neq 0 (
    echo ERROR: Failed to start Docker containers
    echo Check Docker Desktop is running and try again
    pause
    exit /b 1
)

echo ⏳ Waiting for containers to be ready...
timeout /t 3 >nul
docker-compose ps

echo.
echo 🚀 Starting Celery worker in separate window...
start "Celery Worker - Audio Processing" cmd /k "cd /d \"%CD%\" && venv\Scripts\activate.bat && echo Celery Worker for Audio Processing && echo ========================== && celery -A myproject worker --loglevel=info --pool=solo"

echo ⏳ Waiting for Celery to start...
timeout /t 3 /nobreak >nul

echo.
echo 🚀 Starting Django development server...
echo.
echo ✅ All services should be starting!
echo 🌐 Django will be available at: http://127.0.0.1:8000
echo 📊 Redis is running via Docker
echo ⚡ Celery worker is running in separate window
echo.
echo Press Ctrl+C to stop the Django server
echo Don't forget to close the Celery window and stop Docker containers
echo.

python manage.py runserver

echo.
echo 🛑 Django server stopped
echo.
echo To stop all services:
echo 1. Close the Celery worker window
echo 2. Run: docker-compose down
echo.
pause