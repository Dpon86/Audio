@echo off
title Stopping Development Environment
color 0C

echo ================================================================
echo  STOPPING AUDIO DETECTION DEVELOPMENT ENVIRONMENT
echo ================================================================
echo.

echo [1/4] Stopping Django backend...
taskkill /F /FI "WINDOWTITLE eq Django Backend*" >nul 2>&1
echo     √ Django stopped

echo.
echo [2/4] Stopping Celery services...
taskkill /F /FI "WINDOWTITLE eq Celery Worker*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Celery Beat*" >nul 2>&1
echo     √ Celery services stopped

echo.
echo [3/4] Stopping React frontend...
taskkill /F /FI "WINDOWTITLE eq React Frontend*" >nul 2>&1
taskkill /F /IM "node.exe" /T >nul 2>&1
echo     √ React stopped

echo.
echo [4/4] Restoring sleep settings...
powercfg -change -standby-timeout-ac 15 >nul 2>&1
powercfg -change -hibernate-timeout-ac 0 >nul 2>&1
echo     √ Normal sleep behavior restored

echo.
echo ================================================================
echo  ALL SERVICES STOPPED SUCCESSFULLY!
echo ================================================================
echo.
echo Your computer will now sleep normally after 15 minutes of inactivity.
echo.
pause