@echo off
title Docker Cleanup for Audio Detection
color 0E

echo ================================================================
echo  DOCKER CLEANUP - AUDIO DETECTION
echo ================================================================
echo.

echo [1/4] Stopping all Redis containers...
docker stop redis >nul 2>&1
docker stop audio-redis-dev >nul 2>&1
echo     √ Redis containers stopped

echo.
echo [2/4] Removing Redis containers...
docker rm redis >nul 2>&1
docker rm audio-redis-dev >nul 2>&1
echo     √ Redis containers removed

echo.
echo [3/4] Stopping Docker Compose services...
cd backend
docker compose down >nul 2>&1
cd ..
echo     √ Docker Compose services stopped

echo.
echo [4/4] Cleaning up Docker system...
docker system prune -f >nul 2>&1
echo     √ Docker cleanup complete

echo.
echo ================================================================
echo  CLEANUP COMPLETE!
echo ================================================================
echo.
echo All Docker containers and services have been cleaned up.
echo You can now start fresh with ./start-dev-enhanced.bat
echo.
pause