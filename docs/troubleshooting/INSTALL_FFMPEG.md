# 🎵 Install FFmpeg for Audio Transcription

## Problem
Whisper requires FFmpeg to process audio files. You're getting:
```
FileNotFoundError: [WinError 2] The system cannot find the file specified
```

## Solution: Install FFmpeg

### Method 1: Using Chocolatey (Recommended - Easiest)

If you have Chocolatey package manager:

```powershell
# Run PowerShell as Administrator
choco install ffmpeg
```

### Method 2: Using Scoop (Easy)

If you have Scoop package manager:

```powershell
scoop install ffmpeg
```

### Method 3: Manual Installation (Most Common)

1. **Download FFmpeg**:
   - Go to: https://www.gyan.dev/ffmpeg/builds/
   - Download: `ffmpeg-release-essentials.zip` (or latest release)
   - Or direct link: https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-essentials.7z

2. **Extract the Archive**:
   - Extract to: `C:\ffmpeg\`
   - You should have: `C:\ffmpeg\bin\ffmpeg.exe`

3. **Add to System PATH**:
   
   **Option A - Using GUI:**
   - Press `Win + X`, select "System"
   - Click "Advanced system settings"
   - Click "Environment Variables"
   - Under "System variables", find and select "Path"
   - Click "Edit"
   - Click "New"
   - Add: `C:\ffmpeg\bin`
   - Click "OK" on all dialogs

   **Option B - Using PowerShell (Run as Administrator):**
   ```powershell
   [Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\ffmpeg\bin", "Machine")
   ```

4. **Verify Installation**:
   - Close and reopen PowerShell/Terminal
   - Run:
   ```powershell
   ffmpeg -version
   ```
   - You should see FFmpeg version information

### Method 4: Quick Install with PowerShell Script

Run this in PowerShell as Administrator:

```powershell
# Download and install FFmpeg
$ffmpegUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$downloadPath = "$env:TEMP\ffmpeg.zip"
$extractPath = "C:\ffmpeg"

Write-Host "Downloading FFmpeg..." -ForegroundColor Yellow
Invoke-WebRequest -Uri $ffmpegUrl -OutFile $downloadPath

Write-Host "Extracting FFmpeg..." -ForegroundColor Yellow
Expand-Archive -Path $downloadPath -DestinationPath $extractPath -Force

# Find the bin directory (it's usually inside a versioned folder)
$binPath = Get-ChildItem -Path $extractPath -Filter "bin" -Recurse -Directory | Select-Object -First 1
if ($binPath) {
    $ffmpegBin = $binPath.Parent.FullName + "\bin"
    
    # Add to PATH
    Write-Host "Adding to PATH..." -ForegroundColor Yellow
    [Environment]::SetEnvironmentVariable("Path", $env:Path + ";$ffmpegBin", "Machine")
    $env:Path += ";$ffmpegBin"
    
    Write-Host "FFmpeg installed successfully!" -ForegroundColor Green
    Write-Host "Location: $ffmpegBin" -ForegroundColor Cyan
    Write-Host "`nVerifying installation..." -ForegroundColor Yellow
    ffmpeg -version
} else {
    Write-Host "Error: Could not find bin directory" -ForegroundColor Red
}

Remove-Item $downloadPath -Force
```

## After Installation

1. **Close ALL PowerShell/Terminal windows** (PATH changes require restart)
2. **Open new PowerShell window**
3. **Verify FFmpeg is available**:
   ```powershell
   ffmpeg -version
   ```
4. **Restart your Celery worker**:
   ```powershell
   cd C:\Users\NickD\Documents\Github\Audio\backend
   .\venv\Scripts\Activate.ps1
   celery -A myproject worker --loglevel=info --pool=solo
   ```
5. **Try transcription again** in your app

## Troubleshooting

### "ffmpeg is not recognized"
- Make sure you closed and reopened your terminal after adding to PATH
- Verify PATH was updated: `echo $env:Path` should include `C:\ffmpeg\bin`

### Still getting FileNotFoundError
- Restart your Django development server
- Restart your Celery worker
- Restart your computer (to ensure PATH is fully updated)

### Different Error After Installing
- Make sure you downloaded the "essentials" build, not the "full" build
- Try running: `ffmpeg -version` to ensure it works standalone

## What FFmpeg Does

FFmpeg is a multimedia framework that:
- Converts audio/video formats
- Extracts audio from video
- Resamples audio to the format Whisper needs
- Essential for any audio processing in Python

## Alternative: Use FFmpeg-python Package

If you can't install FFmpeg system-wide, you could try:
```powershell
pip install ffmpeg-python
```

However, this still requires the FFmpeg binary to be available.

---

**Once FFmpeg is installed, your transcription will work!** 🎉
