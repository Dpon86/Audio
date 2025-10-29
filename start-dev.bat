@echo off
echo Starting Audio Duplicate Detection Development Environment...
echo.

cd /d "%~dp0backend"

echo [1/9] Checking for existing processes...

REM Check if Django is already running on port 8000
netstat -ano | findstr ":8000.*LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo WARNING: Port 8000 is already in use!
    echo Another Django server or application is running.
    echo.
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (
        echo Process ID using port 8000: %%a
        tasklist /FI "PID eq %%a" | findstr "python"
        if not errorlevel 1 (
            echo This appears to be a Python process.
            echo.
            choice /C YN /M "Do you want to kill this process and continue"
            if errorlevel 2 (
                echo Startup cancelled.
                pause
                exit /b 1
            )
            echo Killing process %%a...
            taskkill /F /PID %%a >nul 2>&1
            timeout /t 2 >nul
        )
    )
)

REM Check if React is already running on port 3000
netstat -ano | findstr ":3000.*LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo WARNING: Port 3000 is already in use!
    echo Another React server or application is running.
    echo.
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000.*LISTENING"') do (
        echo Process ID using port 3000: %%a
        tasklist /FI "PID eq %%a" | findstr "node"
        if not errorlevel 1 (
            echo This appears to be a Node.js process.
            echo.
            choice /C YN /M "Do you want to kill this process and continue"
            if errorlevel 2 (
                echo Startup cancelled.
                pause
                exit /b 1
            )
            echo Killing process %%a...
            taskkill /F /PID %%a >nul 2>&1
            timeout /t 2 >nul
        )
    )
)

echo [2/9] Checking Docker installation...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not installed or not running
    echo Please install Docker Desktop and make sure it's running
    pause
    exit /b 1
)

echo [3/9] Checking Docker Compose...
docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker Compose is not available
    pause
    exit /b 1
)

echo [4/9] Starting Docker containers (Redis + Celery infrastructure)...
docker-compose up -d
if %errorlevel% neq 0 (
    echo ERROR: Failed to start Docker containers
    echo Check Docker Desktop is running and try again
    pause
    exit /b 1
)

echo [5/9] Waiting for containers to be ready...
timeout /t 3 >nul
docker-compose ps

echo [6/9] Running system readiness checks...
python manage.py system_check --fix >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: System check found issues - continuing anyway
    echo Run 'python manage.py system_check --verbose' for details
)

echo [7/9] Starting Celery worker in dedicated console...
start "Celery Worker - Audio Processing" cmd /k "echo Celery Worker for Audio Processing && echo ========================== && celery -A myproject worker --loglevel=info --pool=solo"

echo [8/9] Starting Django development server...
REM Keep the window open with /k instead of /c to prevent it from closing
start "Django Server - Port 8000" cmd /k "python manage.py runserver 8000"

REM Wait for Django to start with retry logic
echo Waiting for Django server to start...
set /a retries=0
set /a max_retries=10

:check_django
timeout /t 2 >nul
netstat -ano | findstr ":8000.*LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo ^[OK^] Django server is running successfully on port 8000!
    goto django_ready
)

set /a retries+=1
if %retries% lss %max_retries% (
    echo Attempt %retries%/%max_retries% - Waiting for Django...
    goto check_django
)

echo.
echo WARNING: Django server didn't respond within 20 seconds.
echo The server window is open - please check it for errors.
echo If you see "Starting development server" message, it's working!
echo.

:django_ready
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

echo [9/9] Starting React development server...
pause >nul

REM Change back to project root, then navigate to frontend
cd /d "%~dp0"
echo Current directory: %CD%
cd frontend\audio-waveform-visualizer
echo Starting React development server from %CD% ...
start "React Frontend" cmd /c "npm start"

pause