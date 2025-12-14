@echo off
echo Checking Docker availability...

docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not installed or not running
    echo Please install Docker Desktop and make sure it's running
    exit /b 1
)

docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker Compose is not available
    echo Please install Docker Compose
    exit /b 1
)

echo Docker and Docker Compose are available
echo Starting audio processing infrastructure...

cd backend
python manage.py start_docker

echo Infrastructure setup complete!
pause