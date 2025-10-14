@echo off
echo Starting Audio Duplicate Detection Development Environment...
echo.

cd /d "%~dp0backend"

echo [1/7] Checking Docker installation...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not installed or not running
    echo Please install Docker Desktop and make sure it's running
    pause
    exit /b 1
)

echo [2/7] Checking Docker Compose...
docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker Compose is not available
    pause
    exit /b 1
)

echo [3/7] Starting Docker containers (Redis + Celery infrastructure)...
docker-compose up -d
if %errorlevel% neq 0 (
    echo ERROR: Failed to start Docker containers
    echo Check Docker Desktop is running and try again
    pause
    exit /b 1
)

echo [4/7] Waiting for containers to be ready...
timeout /t 3 >nul
docker-compose ps

echo [5/7] Running system readiness checks...
python manage.py system_check --fix >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: System check found issues - continuing anyway
    echo Run 'python manage.py system_check --verbose' for details
)

echo [6/7] Starting Celery worker in dedicated console...
start "Celery Worker - Audio Processing" cmd /k "echo Celery Worker for Audio Processing && echo ========================== && celery -A myproject worker --loglevel=info --pool=solo"

echo [7/7] Starting Django development server...
start "Django Server" cmd /c "python manage.py runserver 8000"

echo Docker containers and Celery are now running in dedicated windows
echo.
echo ========================================
echo Development Environment Ready!
echo ========================================
echo Django API: http://localhost:8000
echo Frontend: http://localhost:3000
echo.
echo Docker/Celery Infrastructure:
echo - Containers start automatically during backend startup
echo - Ready immediately for transcription tasks
echo - Auto-shutdown 60 seconds after last task completes
echo.
echo Press any key to continue to frontend setup...
pause >nul

REM Change back to project root, then navigate to frontend
cd /d "%~dp0"
echo Current directory: %CD%
cd frontend\audio-waveform-visualizer
echo Starting React development server from %CD% ...
start "React Frontend" cmd /c "npm start"

pause