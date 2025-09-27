@echo off
REM Audio Repetitive Detection - Development Startup Script
echo ========================================
echo  Audio Repetitive Detection Dev Setup
echo ========================================

set /p START_FRONTEND="Start React frontend too? (y/N): "
if /i "%START_FRONTEND%"=="y" (
    set FRONTEND_FLAG=1
) else (
    set FRONTEND_FLAG=0
)

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
echo 🚀 Starting Redis container...
start "Redis" docker run --rm -p 6379:6379 redis

echo ⏳ Waiting for Redis to start...
timeout /t 5 /nobreak >nul

echo.
echo 🚀 Starting Celery worker...
start "Celery" celery -A myproject worker --loglevel=info --pool=solo

echo ⏳ Waiting for Celery to start...
timeout /t 3 /nobreak >nul

if "%FRONTEND_FLAG%"=="1" (
    echo.
    echo 🚀 Starting React frontend...
    start "React Frontend" cmd /k "cd /d \"C:\Users\user\Documents\GitHub\Audio repetative detection\frontend\audio-waveform-visualizer\" && npm start"
    echo ⏳ Waiting for frontend to start...
    timeout /t 3 /nobreak >nul
)

echo.
echo 🚀 Starting Django development server...
echo.
echo ✅ All services should be starting!
echo 🌐 Django will be available at: http://127.0.0.1:8000
echo 📊 Redis is running on: localhost:6379
echo ⚡ Celery worker is running
if "%FRONTEND_FLAG%"=="1" (
    echo ⚛️  React frontend will be available at: http://localhost:3000
)
echo.
echo Press Ctrl+C in the Django window to stop the server
if "%FRONTEND_FLAG%"=="1" (
    echo Close the React, Redis and Celery windows to stop those services
) else (
    echo Close the Redis and Celery windows to stop those services
    echo To start frontend separately: cd ../frontend/audio-waveform-visualizer && npm start
)
echo.

python manage.py runserver

echo.
echo 🛑 Django server stopped
echo Don't forget to close Redis and Celery windows if needed
pause