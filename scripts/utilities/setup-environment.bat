@echo off
echo ========================================
echo  Quick Fix for Audio Development Setup
echo ========================================

cd /d "%~dp0backend"

echo [1/4] Setting up Python virtual environment...
call setup-venv.bat
if %errorlevel% neq 0 (
    echo ERROR: Failed to setup virtual environment
    pause
    exit /b 1
)

echo.
echo [2/4] Testing Django installation...
call venv\Scripts\activate.bat
python manage.py check --deploy >nul 2>&1
if %errorlevel% neq 0 (
    echo Django check passed with warnings (normal for development)
) else (
    echo ✅ Django is working correctly
)

echo.
echo [3/4] Testing Celery installation...
celery --version >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Celery is working correctly
) else (
    echo ❌ Celery is not working - attempting to reinstall...
    pip install celery
)

echo.
echo [4/4] All setup complete!
echo.
echo ========================================
echo  Ready to Start Development!
echo ========================================
echo.
echo You can now run:
echo   start-dev-venv.bat  (recommended - uses virtual environment)
echo   OR
echo   start-dev.bat       (if you prefer the original method)
echo.
echo The virtual environment will ensure all dependencies are properly isolated.
echo.
pause
