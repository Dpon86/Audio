Write-Host "Starting Frontend..." -ForegroundColor Green

# Navigate to project root if in backend
$currentPath = Get-Location
if ($currentPath.Path.EndsWith("backend")) {
    Set-Location ".."
}

# Navigate to frontend directory
$frontendPath = "frontend\audio-waveform-visualizer"
if (Test-Path $frontendPath) {
    Set-Location $frontendPath
    Write-Host "Starting React from: $(Get-Location)" -ForegroundColor Yellow
    
    # Check if node_modules exists
    if (-not (Test-Path "node_modules")) {
        Write-Host "Installing dependencies..." -ForegroundColor Yellow
        npm install
    }
    
    # Start React server
    Write-Host "Starting React on http://localhost:3000" -ForegroundColor Green
    npm start
} else {
    Write-Host "Frontend directory not found: $frontendPath" -ForegroundColor Red
    Write-Host "Current directory: $(Get-Location)" -ForegroundColor Yellow
}

