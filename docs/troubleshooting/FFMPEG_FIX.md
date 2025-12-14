# 🔧 QUICK FIX: Install FFmpeg

## What Happened
Your transcription failed because **FFmpeg is not installed**.

Whisper needs FFmpeg to process audio files.

## Quick Fix (Choose One Method)

### ⚡ Method 1: Automated Install (Easiest)
Run this in **PowerShell as Administrator**:
```powershell
cd C:\Users\NickD\Documents\Github\Audio
.\install-ffmpeg.ps1
```

### 🍫 Method 2: Chocolatey (If you have it)
```powershell
choco install ffmpeg
```

### 📥 Method 3: Manual Install
1. Download: https://www.gyan.dev/ffmpeg/builds/
2. Extract to `C:\ffmpeg\`
3. Add `C:\ffmpeg\bin` to system PATH
4. Restart terminal

## After Installing FFmpeg

1. **Close ALL terminal windows**
2. **Open new PowerShell**
3. **Verify it works**:
   ```powershell
   ffmpeg -version
   ```
4. **Restart Celery worker**:
   ```powershell
   cd C:\Users\NickD\Documents\Github\Audio\backend
   .\venv\Scripts\Activate.ps1
   celery -A myproject worker --loglevel=info --pool=solo
   ```
5. **Try transcription again!**

## Full Instructions
See **INSTALL_FFMPEG.md** for detailed instructions

---

**This is a one-time setup. Once FFmpeg is installed, transcription will work!** ✅
