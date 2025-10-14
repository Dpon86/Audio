@echo off
title Stopping Simple Development Environment
color 0C

echo ================================================================
echo  STOPPING SIMPLE DEVELOPMENT ENVIRONMENT
echo ================================================================
echo.

echo [1/3] Stopping Django backend...
taskkill /F /FI "WINDOWTITLE eq Django Backend*" >nul 2>&1
taskkill /F /IM "python.exe" /T >nul 2>&1
echo     √ Django stopped

echo.
echo [2/3] Stopping React frontend...
taskkill /F /FI "WINDOWTITLE eq React Frontend*" >nul 2>&1
taskkill /F /IM "node.exe" /T >nul 2>&1
echo     √ React stopped

echo.
echo [3/3] Restoring sleep settings...
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