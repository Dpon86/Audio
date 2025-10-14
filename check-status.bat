@echo off
echo ========================================
echo   Audio Duplicate Detection - System Status
echo ========================================
echo.

cd /d "%~dp0backend"

echo [1/7] Checking Docker Installation...
docker --version >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Docker: INSTALLED
) else (
    echo ❌ Docker: NOT INSTALLED
)

echo [2/7] Checking Redis Container...
docker ps --filter "name=audio-redis-dev" --format "table {{.Names}}\t{{.Status}}" 2>nul | findstr audio-redis-dev >nul
if %errorlevel% equ 0 (
    echo ✅ Redis Container: RUNNING
    docker ps --filter "name=audio-redis-dev" --format "  - {{.Names}}: {{.Status}}"
) else (
    echo ❌ Redis Container: NOT RUNNING
)

echo [3/7] Checking Redis Connectivity...
docker exec audio-redis-dev redis-cli ping >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Redis: RESPONDING TO PING
) else (
    echo ❌ Redis: NOT RESPONDING
)

echo [4/7] Checking Django Backend...
curl -s http://localhost:8000/api/projects/ > nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Django Backend: RUNNING (http://localhost:8000)
) else (
    echo ❌ Django Backend: NOT RUNNING
)

echo [5/7] Checking Celery Worker...
tasklist /FI "WINDOWTITLE eq Celery Worker*" 2>nul | findstr "python" >nul
if %errorlevel% equ 0 (
    echo ✅ Celery Worker: RUNNING
) else (
    echo ❌ Celery Worker: NOT RUNNING
)

echo [6/7] Checking React Frontend...
curl -s http://localhost:3000 > nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ React Frontend: RUNNING (http://localhost:3000)
) else (
    echo ❌ React Frontend: NOT RUNNING
)

echo [7/7] Checking Infrastructure Status...
curl -s http://localhost:8000/api/infrastructure/status/ | findstr "true" >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Infrastructure: READY
) else (
    echo ❌ Infrastructure: NOT READY
)

echo.
echo Status check complete! 
echo To start development environment: run start-dev.bat
echo To see this status again: run check-status.bat
echo.
pause

echo [5/5] Checking Redis Connection...
docker exec backend-redis-1 redis-cli ping >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Redis: CONNECTED
) else (
    echo ❌ Redis: NOT CONNECTED
)

echo.
echo ========================================
echo   System Status Complete
echo ========================================
echo.
echo Access your application at:
echo   Frontend: http://localhost:3000
echo   Backend:  http://localhost:8000/api/
echo.
pause