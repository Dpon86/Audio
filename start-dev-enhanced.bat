@echo off
title Audio Detection - Development Environment
color 0A

echo ================================================================
echo  AUDIO DETECTION - ENHANCED DEVELOPMENT STARTUP
echo ================================================================
echo.

REM Prevent sleep during development
echo [1/6] Configuring system to prevent sleep...
powercfg -change -standby-timeout-ac 0 >nul 2>&1
powercfg -change -hibernate-timeout-ac 0 >nul 2>&1
echo     √ Sleep prevention activated

echo.
echo [2/6] Starting Redis via Docker...

REM First clean up any existing Redis containers to prevent conflicts  
docker stop redis >nul 2>&1
docker rm redis >nul 2>&1
docker stop audio-redis-dev >nul 2>&1  
docker rm audio-redis-dev >nul 2>&1

REM Start fresh Redis container
echo     ! Starting fresh Redis container...
docker run -d --name redis -p 6379:6379 redis:alpine >nul 2>&1
if errorlevel 1 (
    echo     X Failed to start Redis container
    docker --version >nul 2>&1
    if errorlevel 1 (
        echo     X Docker not found. Please install Docker Desktop
        echo       Download from: https://www.docker.com/products/docker-desktop
        pause
        exit /b 1
    ) else (
        echo     X Docker found but Redis failed. Check if port 6379 is in use
        echo       Try running: docker-cleanup.bat first
        pause
        exit /b 1
    )
)

REM Wait for Redis to be ready
echo     ! Waiting for Redis to start...
timeout /t 5 >nul

REM Verify Redis is accessible
docker exec redis redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo     X Redis container started but not responding
    pause
    exit /b 1
)

echo     √ Redis is running

echo.
echo [3/6] Starting Django backend...
cd backend
start "Django Backend" /min cmd /k "python manage.py runserver 8000"
timeout /t 2 >nul

echo.
echo [4/6] Starting Celery worker...
start "Celery Worker" /min cmd /k "python -m celery -A myproject worker --loglevel=info --pool=threads"
timeout /t 3 >nul

echo.
echo [5/6] Starting Celery Beat scheduler...
start "Celery Beat" /min cmd /k "python -m celery -A myproject beat --loglevel=info"
timeout /t 2 >nul

echo.
echo [6/6] Starting React frontend...
cd ..\frontend\audio-waveform-visualizer
start "React Frontend" cmd /k "npm start"

cd ..\..

echo.
echo ================================================================
echo  SUCCESS! DEVELOPMENT ENVIRONMENT STARTED
echo ================================================================
echo.
echo Services running:
echo   • Django Backend:  http://localhost:8000
echo   • React Frontend:  http://localhost:3000  
echo   • Redis Server:    localhost:6379
echo   • Celery Worker:   Background processing
echo   • Celery Beat:     Scheduled tasks
echo.
echo ! IMPORTANT: Keep this window open to maintain services
echo.
echo To stop all services:
echo   1. Press Ctrl+C in this window
echo   2. Or run: ./stop-dev-enhanced.bat
echo.
echo Sleep prevention is ACTIVE - your computer won't sleep
echo Run ./restore-sleep.bat when done to restore normal behavior
echo.
pause

:cleanup
echo.
echo Cleaning up and stopping services...
taskkill /F /IM "python.exe" /T >nul 2>&1
taskkill /F /IM "redis-server.exe" /T >nul 2>&1
powercfg -change -standby-timeout-ac 15 >nul 2>&1
echo Services stopped and sleep settings restored.