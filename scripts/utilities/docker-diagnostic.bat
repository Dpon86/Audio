@echo off
echo ========================================
echo Audio Duplicate Detection - Docker Diagnostic
echo ========================================
echo.

echo [1/5] Checking Docker installation...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not installed
    echo Please install Docker Desktop from: https://www.docker.com/products/docker-desktop
    echo.
    pause
    exit /b 1
) else (
    echo ✓ Docker is installed
    docker --version
)

echo.
echo [2/5] Checking Docker daemon status...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker Desktop is NOT RUNNING
    echo.
    echo SOLUTION: Please start Docker Desktop
    echo 1. Press Windows key and search for "Docker Desktop"
    echo 2. Click on Docker Desktop to start it
    echo 3. Wait for Docker Desktop to fully start (whale icon in system tray)
    echo 4. Run this diagnostic script again
    echo.
    echo Alternative: You can start Docker Desktop from the Start menu
    echo.
    pause
    exit /b 1
) else (
    echo ✓ Docker Desktop is running
)

echo.
echo [3/5] Checking Docker Compose...
docker compose version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker Compose not available
    pause
    exit /b 1
) else (
    echo ✓ Docker Compose is available
    docker compose version
)

echo.
echo [4/5] Testing Docker containers setup...
cd /d "%~dp0backend"
echo Current directory: %cd%
echo Checking docker-compose.yml...
if not exist "docker-compose.yml" (
    echo ❌ docker-compose.yml not found
    pause
    exit /b 1
) else (
    echo ✓ docker-compose.yml found
)

echo.
echo [5/5] Testing Docker containers startup...
echo Starting containers (this may take a few minutes)...
docker compose up -d --build
if %errorlevel% neq 0 (
    echo ❌ Failed to start Docker containers
    echo Check the error messages above
    pause
    exit /b 1
) else (
    echo ✓ Docker containers started successfully
)

echo.
echo Checking container status...
docker compose ps

echo.
echo Testing Redis connection...
timeout /t 5 /nobreak >nul
docker compose exec redis redis-cli ping
if %errorlevel% neq 0 (
    echo ⚠️ Warning: Redis connection test failed
) else (
    echo ✓ Redis is responding
)

echo.
echo ========================================
echo DIAGNOSTIC COMPLETE
echo ========================================
echo.
echo If all checks passed, your Docker setup is ready!
echo You can now start the development server with start-dev.bat
echo.
echo To shut down containers: docker compose down
echo.
pause