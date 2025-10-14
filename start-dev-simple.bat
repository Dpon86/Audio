@echo off
title Audio Detection - Simple Development Startup
color 0A

echo ================================================================
echo  AUDIO DETECTION - SIMPLE DEVELOPMENT STARTUP (No Redis)
echo ================================================================
echo.

REM Prevent sleep during development
echo [1/4] Configuring system to prevent sleep...
powercfg -change -standby-timeout-ac 0 >nul 2>&1
powercfg -change -hibernate-timeout-ac 0 >nul 2>&1
echo     √ Sleep prevention activated

echo.
echo [2/4] Starting Django backend (without Celery)...
cd backend
start "Django Backend" cmd /k "python manage.py runserver 8000"
timeout /t 3 >nul

echo.
echo [3/4] Starting React frontend...
cd ..\frontend\audio-waveform-visualizer
start "React Frontend" cmd /k "npm start"

cd ..\..

echo.
echo [4/4] Development environment ready!
echo.
echo ================================================================
echo  SUCCESS! BASIC DEVELOPMENT ENVIRONMENT STARTED
echo ================================================================
echo.
echo Services running:
echo   • Django Backend:  http://localhost:8000
echo   • React Frontend:  http://localhost:3000  
echo.
echo NOTE: Redis and Celery are NOT running in this mode
echo For background processing, use the full Docker setup
echo.
echo ! IMPORTANT: Keep this window open to maintain services
echo.
echo To stop all services:
echo   1. Press Ctrl+C in this window
echo   2. Or run: ./stop-dev-simple.bat
echo.
echo Sleep prevention is ACTIVE - your computer won't sleep
echo Run ./restore-sleep.bat when done to restore normal behavior
echo.
pause

:cleanup
echo.
echo Cleaning up and stopping services...
taskkill /F /IM "python.exe" /T >nul 2>&1
taskkill /F /IM "node.exe" /T >nul 2>&1
powercfg -change -standby-timeout-ac 15 >nul 2>&1
echo Services stopped and sleep settings restored.