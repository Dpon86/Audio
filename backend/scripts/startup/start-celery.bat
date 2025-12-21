@echo off
REM Start Celery Worker with FFmpeg Support

echo ========================================
echo  Starting Celery Worker with FFmpeg
echo ========================================
echo.

REM Add FFmpeg to PATH
set "PATH=%PATH%;C:\ffmpeg\ffmpeg-8.0-essentials_build\bin"

REM Verify FFmpeg is accessible
echo Checking FFmpeg...
where ffmpeg >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] FFmpeg found in PATH
    ffmpeg -version | findstr "version"
) else (
    echo [ERROR] FFmpeg not found!
    echo Please install FFmpeg first. See INSTALL_FFMPEG.md
    pause
    exit /b 1
)

echo.
echo Activating virtual environment...
REM Navigate to backend root (2 levels up from scripts\startup)
cd /d "%~dp0..\.."
call venv\Scripts\activate.bat

echo.
echo Starting Celery worker...
echo Press Ctrl+C to stop
echo.
echo NOTE: To reload after code changes, restart this window
echo.

celery -A myproject worker --loglevel=info --pool=solo

echo.
echo Celery worker stopped
pause
