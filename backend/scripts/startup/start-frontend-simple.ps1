# Simple Frontend Startup Script
Write-Host "Starting React Frontend..." -ForegroundColor Cyan

# Navigate to frontend directory
$projectRoot = "C:\Users\NickD\Documents\Github\Audio"
$frontendPath = "$projectRoot\frontend\audio-waveform-visualizer"

if (Test-Path $frontendPath) {
    Set-Location $frontendPath
    Write-Host "Starting from: $frontendPath" -ForegroundColor Green
    Write-Host ""
    npm start
} else {
    Write-Host "ERROR: Frontend directory not found!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
}
