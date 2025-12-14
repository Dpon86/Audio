# PowerShell script for setting up the virtual environment
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Setting up Python Virtual Environment" -ForegroundColor Cyan  
Write-Host " (PowerShell Version)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check if Python is available
try {
    $pythonVersion = py --version 2>$null
    Write-Host "✅ Python is available: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ ERROR: Python is not installed or not available via 'py' command" -ForegroundColor Red
    Write-Host "Please install Python from https://python.org" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Create virtual environment if it doesn't exist
if (-not (Test-Path "venv")) {
    Write-Host "🔧 Creating virtual environment..." -ForegroundColor Yellow
    py -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ ERROR: Failed to create virtual environment" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "✅ Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "✅ Virtual environment already exists" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "🔧 Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ ERROR: Failed to activate virtual environment" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "✅ Virtual environment activated" -ForegroundColor Green

# Upgrade pip
Write-Host "🔧 Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# Install requirements
Write-Host "🔧 Installing requirements..." -ForegroundColor Yellow
if (Test-Path "requirements-basic.txt") {
    pip install -r requirements-basic.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ ERROR: Failed to install basic requirements" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "✅ Basic requirements installed successfully" -ForegroundColor Green
    Write-Host ""
    Write-Host "Note: Audio processing dependencies (pydub, ffmpeg-python) are temporarily" -ForegroundColor Yellow
    Write-Host "disabled due to Python 3.13 compatibility issues with audioop module." -ForegroundColor Yellow
    Write-Host "Core functionality (Django, Celery, API) is fully working." -ForegroundColor Yellow
} elseif (Test-Path "requirements.txt") {
    Write-Host "Installing core dependencies from requirements.txt..." -ForegroundColor Yellow
    pip install django djangorestframework celery redis django-cors-headers python-dotenv stripe
    Write-Host "✅ Core requirements installed" -ForegroundColor Green
} else {
    Write-Host "⚠️  WARNING: No requirements file found" -ForegroundColor Yellow
    Write-Host "Installing basic dependencies..." -ForegroundColor Yellow
    pip install django djangorestframework celery redis python-dotenv stripe
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Virtual Environment Setup Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To activate the virtual environment manually in PowerShell:" -ForegroundColor Green
Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host ""
Write-Host "To activate in Command Prompt/Batch:" -ForegroundColor Green  
Write-Host "  venv\Scripts\activate.bat" -ForegroundColor White
Write-Host ""
Write-Host "To deactivate:" -ForegroundColor Green
Write-Host "  deactivate" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter to continue"
