# Deploy Frontend to Production Server
# This script builds the React app locally and deploys it to the Linux server

param(
    [string]$ServerUser = "nickd",
    [string]$ServerIP = "82.165.221.205",
    [string]$ServerPath = "/opt/audioapp/frontend/audio-waveform-visualizer/build/",
    [switch]$SkipBuild,
    [switch]$SkipTransfer,
    [switch]$SkipRestart
)

$ErrorActionPreference = "Stop"

# Colors for output
function Write-Step {
    param([string]$Message)
    Write-Host "`n===> $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

# Get script directory (should be in frontend/audio-waveform-visualizer)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)

Write-Host "========================================" -ForegroundColor Yellow
Write-Host "  Frontend Deployment Script" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host "Project Root: $ProjectRoot"
Write-Host "Frontend Dir: $ScriptDir"
Write-Host "Server: $ServerUser@$ServerIP"
Write-Host ""

# Step 1: Build
if (-not $SkipBuild) {
    Write-Step "Step 1/3: Building React application..."
    
    Push-Location $ScriptDir
    
    # Check if node_modules exists
    if (-not (Test-Path "node_modules")) {
        Write-Host "node_modules not found. Running npm install first..." -ForegroundColor Yellow
        npm install
        if ($LASTEXITCODE -ne 0) {
            Write-Error "npm install failed!"
            Pop-Location
            exit 1
        }
    }
    
    # Check .env.production exists
    if (-not (Test-Path ".env.production")) {
        Write-Error ".env.production not found! Create it first with your production API URL."
        Pop-Location
        exit 1
    }
    
    Write-Host "Building production bundle..."
    npm run build
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Build failed!"
        Pop-Location
        exit 1
    }
    
    # Verify build folder exists
    if (-not (Test-Path "build")) {
        Write-Error "Build folder not created!"
        Pop-Location
        exit 1
    }
    
    $buildSize = (Get-ChildItem build -Recurse | Measure-Object -Property Length -Sum).Sum
    $buildSizeMB = [math]::Round($buildSize / 1MB, 2)
    Write-Success "Build completed successfully! ($buildSizeMB MB)"
    
    Pop-Location
} else {
    Write-Step "Step 1/3: Skipping build (--SkipBuild flag set)"
    
    # Still verify build exists
    if (-not (Test-Path "$ScriptDir\build")) {
        Write-Error "Build folder not found! Cannot skip build."
        exit 1
    }
}

# Step 2: Transfer
if (-not $SkipTransfer) {
    Write-Step "Step 2/3: Transferring files to server..."
    
    Push-Location "$ScriptDir\build"
    
    # Test SSH connection first
    Write-Host "Testing SSH connection..."
    ssh -o ConnectTimeout=5 "$ServerUser@$ServerIP" "echo 'Connection successful'" 2>&1 | Out-Null
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Cannot connect to server! Check your SSH credentials."
        Pop-Location
        exit 1
    }
    
    # Create build directory on server if it doesn't exist
    Write-Host "Ensuring build directory exists on server..."
    ssh "$ServerUser@$ServerIP" "mkdir -p $ServerPath"
    
    # Clear old build files on server
    Write-Host "Clearing old build files..."
    ssh "$ServerUser@$ServerIP" "rm -rf $ServerPath*"
    
    # Transfer files
    Write-Host "Transferring files (this may take a minute)..."
    scp -r * "$ServerUser@${ServerIP}:$ServerPath"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "File transfer failed!"
        Pop-Location
        exit 1
    }
    
    # Verify files were transferred
    $remoteFileCount = ssh "$ServerUser@$ServerIP" "find $ServerPath -type f | wc -l"
    Write-Success "Transfer completed! ($remoteFileCount files transferred)"
    
    Pop-Location
} else {
    Write-Step "Step 2/3: Skipping transfer (--SkipTransfer flag set)"
}

# Step 3: Restart container
if (-not $SkipRestart) {
    Write-Step "Step 3/3: Rebuilding and restarting frontend container..."
    
    Write-Host "Rebuilding frontend container..."
    ssh "$ServerUser@$ServerIP" "cd /opt/audioapp && docker compose -f docker-compose.production.yml build frontend"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Container rebuild failed!"
        exit 1
    }
    
    Write-Host "Restarting frontend container..."
    ssh "$ServerUser@$ServerIP" "cd /opt/audioapp && docker compose -f docker-compose.production.yml up -d frontend"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Container restart failed!"
        exit 1
    }
    
    # Wait a moment for container to start
    Start-Sleep -Seconds 3
    
    # Check container status
    $containerStatus = ssh "$ServerUser@$ServerIP" "docker ps --filter name=audioapp_frontend --format '{{.Status}}'"
    
    if ($containerStatus -match "Up") {
        Write-Success "Frontend container is running!"
        Write-Host "Container status: $containerStatus" -ForegroundColor Gray
    } else {
        Write-Error "Frontend container is not running properly!"
        Write-Host "Checking logs..."
        ssh "$ServerUser@$ServerIP" "docker logs --tail 50 audioapp_frontend"
        exit 1
    }
} else {
    Write-Step "Step 3/3: Skipping container restart (--SkipRestart flag set)"
}

# Final summary
Write-Host "`n========================================" -ForegroundColor Yellow
Write-Host "  Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "Your frontend has been deployed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Visit: https://audio.precisepouchtrack.com" -ForegroundColor White
Write-Host "  2. Test all tabs and features" -ForegroundColor White
Write-Host "  3. Check browser console (F12) for any errors" -ForegroundColor White
Write-Host ""
Write-Host "To view container logs:" -ForegroundColor Cyan
Write-Host "  ssh $ServerUser@$ServerIP" -ForegroundColor White
Write-Host "  docker logs -f audioapp_frontend" -ForegroundColor White
Write-Host ""

# Open browser to test (optional)
$openBrowser = Read-Host "Open browser to test? (y/n)"
if ($openBrowser -eq "y" -or $openBrowser -eq "Y") {
    Start-Process "https://audio.precisepouchtrack.com"
}
