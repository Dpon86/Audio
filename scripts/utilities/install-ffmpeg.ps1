# Quick FFmpeg Installer for Windows
# Run this in PowerShell as Administrator

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  FFmpeg Quick Installer for Windows" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "WARNING: Not running as Administrator" -ForegroundColor Yellow
    Write-Host "You may need admin rights to modify system PATH" -ForegroundColor Yellow
    Write-Host ""
}

# Check if FFmpeg already exists
$existingFFmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($existingFFmpeg) {
    Write-Host "FFmpeg is already installed!" -ForegroundColor Green
    Write-Host "Location: $($existingFFmpeg.Source)" -ForegroundColor Cyan
    ffmpeg -version | Select-Object -First 1
    exit 0
}

Write-Host "Installing FFmpeg..." -ForegroundColor Yellow
Write-Host ""

try {
    # Create directory
    $installPath = "C:\ffmpeg"
    if (-not (Test-Path $installPath)) {
        New-Item -ItemType Directory -Path $installPath -Force | Out-Null
    }

    # Download FFmpeg
    Write-Host "[1/4] Downloading FFmpeg..." -ForegroundColor Cyan
    $ffmpegUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    $downloadPath = "$env:TEMP\ffmpeg.zip"
    
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $ffmpegUrl -OutFile $downloadPath -UseBasicParsing
    $ProgressPreference = 'Continue'
    
    Write-Host "   Downloaded: $('{0:N2}' -f ((Get-Item $downloadPath).Length / 1MB)) MB" -ForegroundColor Green

    # Extract
    Write-Host "[2/4] Extracting FFmpeg..." -ForegroundColor Cyan
    Expand-Archive -Path $downloadPath -DestinationPath $installPath -Force
    
    # Find bin directory
    Write-Host "[3/4] Configuring..." -ForegroundColor Cyan
    $binPath = Get-ChildItem -Path $installPath -Filter "ffmpeg.exe" -Recurse -File | Select-Object -First 1
    
    if ($binPath) {
        $ffmpegBinDir = $binPath.DirectoryName
        Write-Host "   FFmpeg found at: $ffmpegBinDir" -ForegroundColor Green
        
        # Add to PATH
        Write-Host "[4/4] Adding to system PATH..." -ForegroundColor Cyan
        
        # Get current PATH
        $currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
        
        if ($currentPath -notlike "*$ffmpegBinDir*") {
            try {
                [Environment]::SetEnvironmentVariable("Path", "$currentPath;$ffmpegBinDir", "Machine")
                $env:Path += ";$ffmpegBinDir"
                Write-Host "   PATH updated successfully!" -ForegroundColor Green
            } catch {
                Write-Host "   Could not update system PATH (need admin rights)" -ForegroundColor Yellow
                Write-Host "   Please add manually: $ffmpegBinDir" -ForegroundColor Yellow
            }
        } else {
            Write-Host "   Already in PATH!" -ForegroundColor Green
        }
        
        # Cleanup
        Remove-Item $downloadPath -Force -ErrorAction SilentlyContinue
        
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "  FFmpeg Installed Successfully!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "Location: $ffmpegBinDir" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Verifying installation..." -ForegroundColor Yellow
        
        # Test FFmpeg
        & "$ffmpegBinDir\ffmpeg.exe" -version | Select-Object -First 1
        
        Write-Host ""
        Write-Host "NEXT STEPS:" -ForegroundColor Yellow
        Write-Host "1. Close ALL PowerShell/Terminal windows" -ForegroundColor White
        Write-Host "2. Open new PowerShell window" -ForegroundColor White
        Write-Host "3. Restart your Celery worker" -ForegroundColor White
        Write-Host "4. Try transcription again!" -ForegroundColor White
        Write-Host ""
        
    } else {
        Write-Host "Error: Could not find ffmpeg.exe in extracted files" -ForegroundColor Red
        exit 1
    }
    
} catch {
    Write-Host ""
    Write-Host "ERROR: Installation failed" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Please try manual installation from:" -ForegroundColor Yellow
    Write-Host "https://www.gyan.dev/ffmpeg/builds/" -ForegroundColor Cyan
    exit 1
}
