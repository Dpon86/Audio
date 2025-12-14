# PowerShell script for starting the React frontend
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Audio Frontend Development Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check current location
$currentLocation = Get-Location
Write-Host "Current directory: $currentLocation" -ForegroundColor Yellow

# Navigate to project root if we are in backend
if ($currentLocation.Path.EndsWith("backend")) {
    Write-Host "Navigating to project root..." -ForegroundColor Yellow
    Set-Location ".."
    $currentLocation = Get-Location
    Write-Host "New directory: $currentLocation" -ForegroundColor Green
}

# Check if frontend directory exists
$frontendPath = "frontend\audio-waveform-visualizer"
if (-not (Test-Path $frontendPath)) {
    Write-Host "ERROR: Frontend directory not found at $frontendPath" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Frontend directory found: $frontendPath" -ForegroundColor Green

# Navigate to frontend directory
Write-Host "Navigating to frontend directory..." -ForegroundColor Yellow
Set-Location $frontendPath
$frontendLocation = Get-Location
Write-Host "Frontend directory: $frontendLocation" -ForegroundColor Green

# Check if Node.js is installed
Write-Host "Checking Node.js installation..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version 2>$null
    Write-Host "Node.js is available: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Node.js is not installed" -ForegroundColor Red
    Write-Host "Please install Node.js from https://nodejs.org/" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if dependencies are installed
Write-Host "Checking if dependencies are installed..." -ForegroundColor Yellow
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing npm dependencies..." -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install npm dependencies" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "Dependencies installed successfully" -ForegroundColor Green
} else {
    Write-Host "Dependencies already installed" -ForegroundColor Green
}

Write-Host ""
Write-Host "Starting React development server..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Frontend will be available at: http://localhost:3000" -ForegroundColor Cyan
Write-Host "Backend API should be running at: http://localhost:8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop the React server" -ForegroundColor Yellow
Write-Host ""

# Start React development server
npm start
