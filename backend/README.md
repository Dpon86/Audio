# Backend Scripts & Documentation Index

## 📁 Directory Structure

### Startup Scripts (`scripts/startup/`)
- **start-dev-venv.ps1** - ⭐ **Main startup script** - Starts Django, Celery, Redis
- **start-dev-venv.bat** - Batch file version of main startup
- **start-celery.bat** - Standalone Celery worker with FFmpeg support
- **restart-celery.ps1** - Restart Celery worker only
- **start-dev.bat** - Alternative startup script
- **start-dev.sh** - Linux/Mac startup script

### Setup Scripts (`scripts/setup/`)
- **setup-venv.ps1** - ⭐ **Run this first** - Creates virtual environment & installs dependencies
- **setup-venv.bat** - Batch file version of setup

### Documentation (`docs/`)
- **QUICK_REFERENCE.txt** - Quick command reference
- **ALL_SCRIPTS_FIXED.md** - Script fixes documentation
- **COMPLETE_SOLUTION.md** - Complete setup solution
- **How_to_guide** - General how-to guide

## 🚀 Quick Start

### First Time Setup
```powershell
cd backend
.\scripts\setup\setup-venv.ps1
```

### Start Development Environment
```powershell
cd backend
.\scripts\startup\start-dev-venv.ps1
```

### Restart Just Celery
```powershell
cd backend
.\scripts\startup\restart-celery.ps1
```

## 📝 Important Files (Root Level)

- **manage.py** - Django management commands
- **requirements.txt** - Production dependencies
- **requirements-basic.txt** - Core dependencies (recommended)
- **requirements-minimal.txt** - Minimal dependencies
- **docker-compose.yml** - Docker configuration for Redis
- **Dockerfile** - Docker image configuration
- **.env.template** - Environment variables template
- **db.sqlite3** - SQLite database

## 🔧 Configuration

### Environment Variables
Copy `.env.template` to `.env` and configure:
- Database settings
- Stripe API keys
- Redis configuration
- Django secret key

### Docker
Redis runs in Docker via `docker-compose.yml`
- Port: 6379
- Used by Celery for task queue

## 🎯 Common Tasks

**Run Django commands:**
```powershell
cd backend
.\venv\Scripts\Activate.ps1
python manage.py <command>
```

**Create superuser:**
```powershell
python manage.py createsuperuser
```

**Run migrations:**
```powershell
python manage.py migrate
```

**Collect static files:**
```powershell
python manage.py collectstatic
```

## 🗂️ Application Structure

- **accounts/** - User authentication & billing
- **audioDiagnostic/** - Audio processing & transcription
- **myproject/** - Django project settings
- **media/** - Uploaded audio files
- **venv/** - Python virtual environment (created by setup script)
