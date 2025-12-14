# PowerShell script for starting development environment
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Audio Duplicate Detection Dev Setup" -ForegroundColor Cyan
Write-Host " (PowerShell Version with Virtual Environment)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check if virtual environment exists
if (-not (Test-Path "venv\Scripts\Activate.ps1")) {
    Write-Host "ERROR: Virtual environment not found!" -ForegroundColor Red
    Write-Host "Please run setup-venv.ps1 first to create the virtual environment" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Add FFmpeg to PATH if it exists
$ffmpegPath = "C:\ffmpeg\ffmpeg-8.0-essentials_build\bin"
if (Test-Path $ffmpegPath) {
    $env:Path += ";$ffmpegPath"
    Write-Host "FFmpeg added to PATH for this session" -ForegroundColor Green
} else {
    Write-Host "WARNING: FFmpeg not found at $ffmpegPath" -ForegroundColor Yellow
    Write-Host "Audio transcription may not work. See INSTALL_FFMPEG.md" -ForegroundColor Yellow
}

Write-Host "Virtual environment activated" -ForegroundColor Green
Write-Host "Current Python:" -ForegroundColor Green
python --version
Write-Host "Python location:" -ForegroundColor Green
where.exe python

Write-Host ""
Write-Host "Checking Docker..." -ForegroundColor Yellow
try {
    docker --version | Out-Null
    Write-Host "Docker is available" -ForegroundColor Green
} catch {
    Write-Host "Docker is not installed or not running" -ForegroundColor Red
    Write-Host "Please install Docker Desktop and make sure it is running" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Starting Docker containers (Redis)..." -ForegroundColor Yellow
docker-compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to start Docker containers" -ForegroundColor Red
    Write-Host "Check Docker Desktop is running and try again" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Waiting for containers to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 3
docker-compose ps

Write-Host ""
Write-Host "Starting Celery worker in separate window..." -ForegroundColor Yellow
$currentPath = (Get-Location).Path
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "cd /d `"$currentPath`" && start-celery.bat" -WindowStyle Normal

Write-Host "Waiting for Celery to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "Starting Django development server..." -ForegroundColor Yellow
Write-Host ""
Write-Host "All services should be starting!" -ForegroundColor Green
Write-Host "Django will be available at: http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "Redis is running via Docker" -ForegroundColor Cyan
Write-Host "Celery worker is running in separate window" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop the Django server" -ForegroundColor Yellow
Write-Host "Do not forget to close the Celery window and stop Docker containers" -ForegroundColor Yellow
Write-Host ""

# Start Django server
python manage.py runserver

Write-Host ""
Write-Host "Django server stopped" -ForegroundColor Yellow
Write-Host ""
Write-Host "To stop all services:" -ForegroundColor Yellow
Write-Host "1. Close the Celery worker window" -ForegroundColor White
Write-Host "2. Run: docker-compose down" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter to continue"
