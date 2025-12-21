@echo off
echo Stopping Audio Duplicate Detection Development Environment...
echo.

echo [1/6] Stopping Django development server...
REM Kill by window title
taskkill /F /FI "WINDOWTITLE eq Django Server*" >nul 2>&1
REM Also kill any Python process on port 8000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING" 2^>nul') do (
    tasklist /FI "PID eq %%a" | findstr "python" >nul 2>&1
    if not errorlevel 1 (
        echo Killing Django process on port 8000 (PID: %%a)
        taskkill /F /PID %%a >nul 2>&1
    )
)
echo ✅ Django server stopped

echo [2/6] Stopping React development server...
REM Kill by window title
taskkill /F /FI "WINDOWTITLE eq React Frontend*" >nul 2>&1
REM Also kill any Node process on port 3000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000.*LISTENING" 2^>nul') do (
    tasklist /FI "PID eq %%a" | findstr "node" >nul 2>&1
    if not errorlevel 1 (
        echo Killing React process on port 3000 (PID: %%a)
        taskkill /F /PID %%a >nul 2>&1
    )
)
echo ✅ React server stopped

echo [3/6] Stopping Celery worker...
taskkill /F /FI "WINDOWTITLE eq Celery Worker*" >nul 2>&1
echo ✅ Celery worker stopped

echo [4/6] Stopping Docker containers...
cd /d "%~dp0..\..\backend"
docker compose down >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Docker containers stopped
) else (
    docker stop redis >nul 2>&1
    if %errorlevel% equ 0 (
        echo ✅ Redis container stopped
    ) else (
        echo ⚠️ Docker containers were not running
    )
)
cd /d "%~dp0"

echo [5/6] Cleaning up orphaned containers...
docker container prune -f >nul 2>&1

echo [6/6] Verifying ports are free...
netstat -ano | findstr ":8000.*LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo ⚠️ WARNING: Port 8000 is still in use!
) else (
    echo ✅ Port 8000 is free
)

netstat -ano | findstr ":3000.*LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo ⚠️ WARNING: Port 3000 is still in use!
) else (
    echo ✅ Port 3000 is free
)

echo.
echo Development environment stopped successfully!
echo Run start-dev.bat to start again.
echo.
pause