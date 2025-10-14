@echo off
echo Stopping Audio Duplicate Detection Development Environment...
echo.

cd /d "%~dp0backend"

echo [1/4] Stopping Django development server...
taskkill /F /FI "WINDOWTITLE eq Django Server" >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Django server stopped
) else (
    echo ⚠️ Django server was not running
)

echo [2/4] Stopping Celery worker...
taskkill /F /FI "WINDOWTITLE eq Celery Worker*" >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Celery worker stopped
) else (
    echo ⚠️ Celery worker was not running
)

echo [3/4] Stopping Docker containers...
docker-compose down >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Docker containers stopped
) else (
    echo ⚠️ Docker containers were not running
)

echo [4/4] Cleaning up orphaned containers...
docker container prune -f >nul 2>&1

echo.
echo Development environment stopped successfully!
echo Run start-dev.bat to start again.
echo.
pause