# 🚀 QUICK START GUIDE - Your Working Setup

## ✅ What Works on Your Device

Based on the analysis, here are the **WORKING** methods to start your development environment:

---

## 🎯 METHOD 1: Separate Backend & Frontend (RECOMMENDED)

This is the **most reliable** method for your setup.

### Step 1: Start Backend (Django + Celery + Redis)

**Open PowerShell Terminal #1:**
```powershell
cd C:\Users\NickD\Documents\Github\Audio\backend
.\start-dev-venv.ps1
```

**What this does:**
- ✅ Activates virtual environment
- ✅ Starts Docker/Redis
- ✅ Starts Celery worker
- ✅ Starts Django on http://localhost:8000

---

### Step 2: Start Frontend (React)

**Open PowerShell Terminal #2:**
```powershell
cd C:\Users\NickD\Documents\Github\Audio
.\start-frontend.ps1
```

**What this does:**
- ✅ Checks Node.js installation
- ✅ Installs npm dependencies (if needed)
- ✅ Starts React on http://localhost:3000

---

## 🎯 METHOD 2: Manual Control (Full Transparency)

If you want complete control over each service:

### Terminal 1: Django
```powershell
cd C:\Users\NickD\Documents\Github\Audio\backend
.\venv\Scripts\Activate.ps1
python manage.py runserver
```

### Terminal 2: Frontend
```powershell
cd C:\Users\NickD\Documents\Github\Audio\frontend\audio-waveform-visualizer
npm start
```

### Terminal 3: Celery (Optional)
```powershell
cd C:\Users\NickD\Documents\Github\Audio\backend
.\venv\Scripts\Activate.ps1
celery -A myproject worker --loglevel=info --pool=solo
```

---

## 🎯 METHOD 3: Backend Only (API Development)

If you only need the API (no frontend):

```powershell
cd C:\Users\NickD\Documents\Github\Audio\backend
.\start-dev-venv.ps1
```

Then use:
- Postman for API testing
- Django Admin: http://localhost:8000/admin
- API endpoints: http://localhost:8000/api/

---

## ❌ Scripts That DON'T Work

### Don't Use These:
1. ❌ `start-dev.bat` (root folder) - **Wrong frontend path**
2. ❌ `start-dev-simple.bat` - **No virtual environment**
3. ❌ `backend/start-dev.bat` (old version) - **Missing venv activation**

### Why They Fail:
- Hardcoded wrong user paths (`C:\Users\user\...`)
- No virtual environment activation
- Using `python` instead of `py` or venv python

---

## 📋 Complete Startup Checklist

### First Time Setup:
- [ ] Python 3.13.5 installed ✅ (Already done)
- [ ] Virtual environment created ✅ (Already done)
- [ ] Dependencies installed ✅ (Already done)
- [ ] Docker Desktop running ✅ (Required)
- [ ] Node.js installed (Check: `node --version`)

### Every Time You Start:
1. **Make sure Docker Desktop is running**
2. **Open Terminal 1** → Start backend (`.\backend\start-dev-venv.ps1`)
3. **Open Terminal 2** → Start frontend (`.\start-frontend.ps1`)
4. **Wait ~30 seconds** for services to initialize
5. **Open browser** → http://localhost:3000

---

## 🐛 Troubleshooting

### "Port 8000 already in use"
```powershell
# Find and kill the process
netstat -ano | findstr :8000
taskkill /F /PID <PID_NUMBER>
```

### "Port 3000 already in use"
```powershell
# Find and kill the process
netstat -ano | findstr :3000
taskkill /F /PID <PID_NUMBER>
```

### "Docker is not running"
- Open Docker Desktop
- Wait for it to fully start (whale icon in system tray)
- Try again

### "Virtual environment not found"
```powershell
cd C:\Users\NickD\Documents\Github\Audio\backend
.\setup-venv.ps1
```

### "npm not found"
- Install Node.js from https://nodejs.org/
- Restart PowerShell after installation

---

## 🎨 Visual Guide

```
┌─────────────────────────────────────────────────────┐
│  Terminal 1: Backend (Django + Celery + Redis)     │
│  C:\...\Audio\backend> .\start-dev-venv.ps1        │
│  Status: ✅ Running on http://localhost:8000       │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  Terminal 2: Frontend (React)                       │
│  C:\...\Audio> .\start-frontend.ps1                │
│  Status: ✅ Running on http://localhost:3000       │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  Browser                                             │
│  http://localhost:3000 → React App                  │
│  http://localhost:8000 → Django API                 │
│  http://localhost:8000/admin → Django Admin         │
└─────────────────────────────────────────────────────┘
```

---

## 📝 Summary

### ✅ WORKING Scripts:
- `backend/start-dev-venv.ps1` - Backend with venv
- `backend/start-dev-venv.bat` - Backend with venv (CMD)
- `start-frontend.ps1` - Frontend starter
- `backend/setup-venv.ps1` - Environment setup

### ⚠️ Use With Caution:
- `backend/setup-venv.bat` - Works but PS1 is better

### ❌ DON'T USE:
- `start-dev.bat` (root) - Broken paths
- `start-dev-simple.bat` - No venv
- `backend/start-dev.bat` (old) - Outdated

---

## 🎯 Your Best Workflow

**Most Reliable Setup:**
1. One PowerShell for backend: `.\backend\start-dev-venv.ps1`
2. One PowerShell for frontend: `.\start-frontend.ps1`
3. Both services running independently
4. Easy to restart either service separately
5. Clear error messages if something fails

**Start coding! 🚀**
