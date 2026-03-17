# 🔧 RESTART CELERY WITH FFMPEG - Quick Guide

## The Problem
Your Celery worker started before FFmpeg was added to PATH, so it can't find FFmpeg.

## The Solution: Restart Celery

### Method 1: Use the New Restart Script (Easiest!)

1. **Close the Celery window** (the CMD window showing Celery logs)
2. **Open PowerShell** in backend directory
3. **Run**:
   ```powershell
   cd C:\Users\NickD\Documents\Github\Audio\backend
   .\restart-celery.ps1
   ```

This script automatically:
- Activates virtual environment
- Adds FFmpeg to PATH
- Starts Celery worker
- Verifies FFmpeg is accessible

### Method 2: Restart Everything (Also Easy!)

1. **Close the Celery window**
2. **Press Ctrl+C** in the Django terminal
3. **Run**:
   ```powershell
   cd C:\Users\NickD\Documents\Github\Audio\backend
   .\start-dev-venv.ps1
   ```

This starts Django + Celery + Redis all together (with FFmpeg support built in now).

### Method 3: Manual Restart

If you prefer to do it manually:

1. **Close the Celery window**
2. **Open new PowerShell**
3. **Run**:
   ```powershell
   cd C:\Users\NickD\Documents\Github\Audio\backend
   .\venv\Scripts\Activate.ps1
   $env:Path += ";C:\ffmpeg\ffmpeg-8.0-essentials_build\bin"
   celery -A myproject worker --loglevel=info --pool=solo
   ```

## After Restarting

1. ✅ Celery worker is running with FFmpeg
2. ✅ Try transcription in your app
3. ✅ It should work perfectly now!

## What Changed

The following scripts now automatically include FFmpeg:
- ✅ `backend/start-dev-venv.ps1` - Auto-adds FFmpeg to PATH
- ✅ `backend/restart-celery.ps1` - NEW! Dedicated Celery restart with FFmpeg

## Verify It's Working

After restarting, you should see in the Celery logs:
- No more `FileNotFoundError: [WinError 2]`
- Whisper will successfully process audio files
- Transcription progress will complete

---

**Just close that Celery window and restart it - you're almost there!** 🚀
