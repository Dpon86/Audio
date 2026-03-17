# Documentation Index

## 📁 Directory Structure

### Architecture & Planning (`architecture/`)
- **AI_CODING_PROMPT.md** - AI coding assistant guidelines
- **ARCHITECTURE.md** - System architecture overview
- **IMPLEMENTATION_SUMMARY.md** - Implementation details and summary
- **PRODUCTION_DEPLOYMENT.md** - Production deployment guide

### Setup Guides (`setup-guides/`)
- **START_HERE.md** - ⭐ **Main setup guide - READ THIS FIRST**
- **QUICK_START_WORKING.md** - Quick start instructions
- **SETUP_COMPLETE.md** - Setup completion verification
- **SETUP_FIX.md** - Common setup fixes
- **STARTUP_COMPATIBILITY_ANALYSIS.md** - Script compatibility analysis
- **WORKING_SCRIPTS_FINAL.md** - Final working scripts reference

### Troubleshooting (`troubleshooting/`)
- **FFMPEG_FIXED_CODE_LEVEL.md** - ⭐ **FFmpeg final fix - Code level solution**
- **FINAL_FIX_CELERY.md** - Celery worker FFmpeg integration
- **INSTALL_FFMPEG.md** - Complete FFmpeg installation guide
- **FFMPEG_FIX.md** - Quick FFmpeg fix
- **FFMPEG_INSTALLED.md** - FFmpeg installation confirmation
- **RESTART_CELERY_NOW.md** - Celery restart instructions
- **DO_THIS_NOW.md** - Quick troubleshooting steps
- **POWERSHELL_FIX.md** - PowerShell script fixes
- **FIXED_SCRIPT.md** - Script fix documentation

## 🚀 Quick Start

1. Read **docs/setup-guides/START_HERE.md**
2. Run commands from **COMMANDS.txt** (in root directory)
3. If issues arise, check **docs/troubleshooting/**

## 📜 Scripts

### Root Startup Scripts (`../scripts/startup/`)
- **start-frontend.ps1** / **start-frontend-simple.ps1** - Frontend startup

### Root Utility Scripts (`../scripts/utilities/`)
- **install-ffmpeg.ps1** - Automated FFmpeg installer
- **docker-cleanup.bat** / **docker-diagnostic.bat** - Docker utilities
- **setup-docker.bat** / **setup-environment.bat** - Environment setup
- **check-status.bat** - System status checker
- **prevent-sleep.bat** / **restore-sleep.bat** - Sleep prevention utilities
- **check_user.py** / **test_authentication.py** - Testing utilities
- Plus old startup scripts (start-dev.bat, stop-dev.bat, etc.)

### Backend Scripts (`../backend/scripts/`)
**Startup** (`startup/`)
- **start-dev-venv.ps1** - ⭐ Main backend startup (Django + Celery + Redis)
- **start-celery.bat** - Standalone Celery with FFmpeg
- **restart-celery.ps1** - Restart Celery worker
- **start-dev-venv.bat** / **start-dev.bat** / **start-dev.sh** - Alternative startup options

**Setup** (`setup/`)
- **setup-venv.ps1** - ⭐ Virtual environment setup
- **setup-venv.bat** - Batch version of setup

## 🔗 External References

- **README.md** (root) - Project overview
- **COMMANDS.txt** (root) - ⭐ Quick command reference (UPDATED PATHS)
- **backend/README.md** - Backend scripts & setup guide
- **backend/** - Django backend code
- **frontend/** - React frontend code
