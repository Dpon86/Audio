# 🎯 DO THIS NOW - Simple 3-Step Fix

## The Problem
Your Celery worker can't find FFmpeg because of how Windows CMD handles PATH.

## The Fix (Takes 30 seconds)

### Step 1: Close Celery
Find the **CMD window** showing Celery logs and **close it** (click X).

### Step 2: Restart Backend
In PowerShell, run:
```powershell
cd C:\Users\NickD\Documents\Github\Audio\backend
.\start-dev-venv.ps1
```

### Step 3: Try Transcription
Go to http://localhost:3000 and try transcribing again.

---

## What Changed
- Created `backend/start-celery.bat` that properly includes FFmpeg
- Updated `start-dev-venv.ps1` to use this new batch file
- The Celery worker window will now have FFmpeg available

## Verify It Worked
When the new Celery window opens, you should see:
```
[OK] FFmpeg found in PATH
ffmpeg version 8.0-essentials_build
```

---

**That's it! Close → Restart → Try transcription** 🚀
