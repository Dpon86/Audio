# Restart Celery Worker with FFmpeg Support
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Celery Worker Restart (with FFmpeg)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Navigate to backend root (2 levels up from scripts\startup)
$backendRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $backendRoot

# Check if we're in the backend directory
if (-not (Test-Path "manage.py")) {
    Write-Host "ERROR: Not in backend directory" -ForegroundColor Red
    Write-Host "Please run from backend folder or use: backend\scripts\startup\restart-celery.ps1" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if virtual environment exists
if (-not (Test-Path "venv\Scripts\Activate.ps1")) {
    Write-Host "ERROR: Virtual environment not found!" -ForegroundColor Red
    Write-Host "Please run scripts\setup\setup-venv.ps1 first" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Add FFmpeg to PATH
$ffmpegPath = "C:\ffmpeg\ffmpeg-8.0-essentials_build\bin"
if (Test-Path $ffmpegPath) {
    $env:Path += ";$ffmpegPath"
    Write-Host "FFmpeg added to PATH" -ForegroundColor Green
    
    # Verify FFmpeg is accessible
    try {
        $ffmpegVersion = & ffmpeg -version 2>&1 | Select-Object -First 1
        Write-Host "FFmpeg verified: $ffmpegVersion" -ForegroundColor Green
    } catch {
        Write-Host "WARNING: FFmpeg found but not accessible" -ForegroundColor Yellow
    }
} else {
    Write-Host "ERROR: FFmpeg not found at $ffmpegPath" -ForegroundColor Red
    Write-Host "Please install FFmpeg first. See INSTALL_FFMPEG.md" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Starting Celery worker..." -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

# Start Celery
celery -A myproject worker --loglevel=info --pool=solo
