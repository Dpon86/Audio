# Audio App Deployment Guide

Complete reference for deploying backend and frontend updates to the production server.

> **📚 For system architecture and troubleshooting:** See [ARCHITECTURE.md](./ARCHITECTURE.md)

---

## Table of Contents
1. [Backend Deployment (GitHub)](#backend-deployment-github)
2. [Frontend Deployment (Local Build)](#frontend-deployment-local-build)
3. [Full Stack Deployment (Both)](#full-stack-deployment-both)
4. [Verification & Testing](#verification--testing)
5. [Troubleshooting](#troubleshooting)
6. [Quick Reference Commands](#quick-reference-commands)

---

## Backend Deployment (GitHub)

Backend code is managed via Git and deployed by pulling changes from the repository.

### Prerequisites
- Changes committed and pushed to GitHub repository
- SSH access to server: `82.165.221.205`

### Step-by-Step Process

#### 1. Connect to Server
```bash
ssh nickd@82.165.221.205
cd /opt/audioapp
```

#### 2. Check for Updates
```bash
# See what's available to pull
git fetch origin
git log --oneline HEAD..origin/master

# Preview changes
git show --stat <commit-hash>
```

#### 3. Pull Changes
```bash
# Stash any local changes (if needed)
git stash

# Pull from GitHub
git pull origin master

# Reapply stashed changes (if needed)
git stash pop
```

#### 4. Rebuild Docker Images (CRITICAL!)

**⚠️ MOST IMPORTANT STEP - Backend code is BAKED into Docker images!**

The containers use Dockerfiles, NOT volume mounts. When you `git pull`, it only updates the HOST filesystem. The containers still have OLD code from when they were last built.

**You MUST rebuild the images:**

```bash
# Rebuild backend and celery with new code
cd /opt/audioapp
docker-compose -f docker-compose.production.yml up -d --build backend celery_worker
```

**What happens:**
1. `git pull` → Updates `/opt/audioapp/backend/` **on the host**
2. `docker-compose build` → Copies code from host → Docker image
3. `docker-compose up -d` → Recreates containers from new image
4. Containers now have NEW code!

**Without rebuild:**
- Host has new code ✅
- Containers have old code ❌
- Bugs persist! ❌

##### Option A: Rebuild Both (Recommended)
```bash
# Rebuild and recreate backend + celery
cd /opt/audioapp
docker-compose -f docker-compose.production.yml up -d --build backend celery_worker
```

##### Option B: Restart Only What Changed

**For Celery tasks** (`duplicate_tasks.py`, `transcription_tasks.py`, etc.):
```bash
docker restart audioapp_celery_worker
```

**For Django views/models** (`views.py`, `models.py`, `serializers.py`):
```bash
touch backend/myproject/wsgi.py
```

**For settings** (`settings.py`):
```bash
touch backend/myproject/wsgi.py
docker restart audioapp_celery_worker
```

#### 5. Verify Backend Deployment

**⚠️ CRITICAL CHECK:** Verify containers REBUILT and are running NEW code!

```bash
# Check when containers were created (should be < 1 minute if just rebuilt)
docker ps --filter name=audioapp_celery_worker --format "{{.Names}}: Created {{.CreatedAt}} | Status: {{.Status}}"
docker ps --filter name=audioapp_backend --format "{{.Names}}: Created {{.CreatedAt}} | Status: {{.Status}}"

# If created days/hours ago, you forgot to rebuild!
# You MUST rebuild to get new code from host into containers

# Verify Celery worker loaded tasks and is ready
docker logs --tail 50 audioapp_celery_worker | grep "ready"

# Should see: [TIMESTAMP: INFO/MainProcess] celery@HOSTNAME ready.
# Timestamp should be very recent (within last minute)

# Check code is actually in the container
docker exec audioapp_celery_worker grep -n "project = None" /app/audioDiagnostic/tasks/duplicate_tasks.py || echo "Fix not in container!"

# Check Django backend is responding
curl -s http://localhost:8001/api/health/ || echo "Check Django logs"

# Check for recent errors (look at timestamps!)
docker logs --tail 100 audioapp_celery_worker | grep -i error
```

**Common Mistake:** Git pull succeeds but images NOT rebuilt = old code still in containers!

**How to Check:**
```bash
# Quick check: Were containers recreated after git pull?
echo "Container created:" && docker inspect audioapp_celery_worker --format '{{.Created}}'
echo "Last git pull:" && cd /opt/audioapp && git log -1 --format="%ai"

# If git pull is newer than container creation, you forgot to rebuild!

# If uptime > 1 hour and you just pulled code, you forgot to restart!
```

### Backend File Locations

| Component | Path | Requires Restart |
|-----------|------|------------------|
| Celery Tasks | `/opt/audioapp/backend/audioDiagnostic/tasks/*.py` | Celery Worker |
| Django Views | `/opt/audioapp/backend/audioDiagnostic/views/*.py` | Django (wsgi.py) |
| Django Models | `/opt/audioapp/backend/audioDiagnostic/models.py` | Django (wsgi.py) |
| Settings | `/opt/audioapp/backend/myproject/settings.py` | Both |
| Serializers | `/opt/audioapp/backend/api/Serializers/*.py` | Django (wsgi.py) |
| URLs | `/opt/audioapp/backend/api/urls.py` | Django (wsgi.py) |

---

## Frontend Deployment (Local Build)

Frontend is built on your **Windows machine** and uploaded to the server.

### Prerequisites
- Node.js installed on Windows machine
- Frontend changes ready to build
- scp/ssh access to server

### Step-by-Step Process

#### 1. Build on Windows Machine
```powershell
# Navigate to frontend directory
cd C:\Users\NickD\Documents\Github\Audio\frontend\audio-waveform-visualizer

# Build the React app
npm run build
```

Expected output:
```
File sizes after gzip:
  360.15 kB  build\static\js\main.HASH.js
  27.57 kB   build\static\css\main.HASH.css
```

#### 2. Upload Build to Server
```powershell
# Upload all build files
scp -r build\* nickd@82.165.221.205:/opt/audioapp/frontend/build/
```

#### 3. Deploy on Server

**From Windows (recommended):**
```powershell
ssh nickd@82.165.221.205 "FRONTEND_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'audioapp_frontend|_audioapp_frontend' | head -1) && rsync -av --delete --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r /opt/audioapp/frontend/build/ /opt/audioapp/frontend/audio-waveform-visualizer/build/ && if [ -n \"$FRONTEND_CONTAINER\" ]; then docker cp /opt/audioapp/frontend/build/. $FRONTEND_CONTAINER:/usr/share/nginx/html/ && docker restart $FRONTEND_CONTAINER; fi && sudo chmod -R u=rwX,go=rX /opt/audioapp/frontend/audio-waveform-visualizer/build/ && sudo chown -R nickd:www-data /opt/audioapp/frontend/audio-waveform-visualizer/build/ && sudo systemctl reload nginx"
```

**From Server:**
```bash
# Deploy to main nginx
rsync -av --delete --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r /opt/audioapp/frontend/build/ /opt/audioapp/frontend/audio-waveform-visualizer/build/

# Deploy to Docker container
FRONTEND_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'audioapp_frontend|_audioapp_frontend' | head -1)
if [ -n "$FRONTEND_CONTAINER" ]; then
  docker cp /opt/audioapp/frontend/build/. $FRONTEND_CONTAINER:/usr/share/nginx/html/
  docker restart $FRONTEND_CONTAINER
fi

# Fix permissions for nginx (critical!)
sudo chmod -R u=rwX,go=rX /opt/audioapp/frontend/audio-waveform-visualizer/build/
sudo chown -R nickd:www-data /opt/audioapp/frontend/audio-waveform-visualizer/build/

# Reload main nginx
sudo systemctl reload nginx
```

#### 3.1 Critical Check: Which Path Is Actually Serving Production?

Before troubleshooting "old frontend still showing", verify which source is live for https://audio.precisepouchtrack.com.

```bash
# Show active server block and frontend root for production domain
sudo nginx -T 2>/dev/null | grep -nE 'server_name audio.precisepouchtrack.com|root /opt/audioapp/frontend|location /\s*\{|proxy_pass'

# Check hash in nginx production root (this is what public SSL domain serves)
grep -o 'main\.[^"]*\.js' /opt/audioapp/frontend/audio-waveform-visualizer/build/index.html

# Check hash in upload staging directory
grep -o 'main\.[^"]*\.js' /opt/audioapp/frontend/build/index.html
```

If hashes differ, production is still on old assets until you run the rsync step.

#### 3.2 Quick Fix For Hash Mismatch

```bash
# Sync uploaded build into nginx live root and reload nginx
rsync -av --delete --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r /opt/audioapp/frontend/build/ /opt/audioapp/frontend/audio-waveform-visualizer/build/
sudo systemctl reload nginx
```

#### 3.3 Critical: Fix File Permissions for Nginx

**⚠️ IMPORTANT:** If you uploaded files directly via SCP (bypassing rsync --chmod), nginx may not be able to read them, causing 404 errors for CSS/JS files.

**Symptoms:**
- Browser console shows: `Failed to load main.HASH.js: 404 (Not Found)`
- Nginx error log shows: `stat() failed (13: Permission denied)`

**Fix:**
```bash
# Fix permissions so nginx (www-data) can read all build files
sudo chmod -R u=rwX,go=rX /opt/audioapp/frontend/audio-waveform-visualizer/build/
sudo chown -R nickd:www-data /opt/audioapp/frontend/audio-waveform-visualizer/build/

# Reload nginx to apply changes
sudo systemctl reload nginx
```

**Verify permissions are correct:**
```bash
# Check critical files are readable by nginx
ls -la /opt/audioapp/frontend/audio-waveform-visualizer/build/static/js/main.*.js | head -1
ls -la /opt/audioapp/frontend/audio-waveform-visualizer/build/static/css/main.*.css | head -1

# Should show: -rw-r--r-- 1 nickd www-data (nginx can read)
# NOT:         -rw-rw-r-- 1 nickd nickd (nginx cannot read)
```

**Check nginx error log if 404s persist:**
```bash
sudo tail -20 /var/log/nginx/error.log | grep -E "Permission denied|static"
```

#### 4. Verify Frontend Deployment
```bash
# Check production nginx root hash (public domain source of truth)
grep -o 'main\.[^"]*\.js' /opt/audioapp/frontend/audio-waveform-visualizer/build/index.html

# Check uploaded build hash (staging upload folder)
grep -o 'main\.[^"]*\.js' /opt/audioapp/frontend/build/index.html

# Optional: check container hash used for port 3001 path
FRONTEND_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'audioapp_frontend|_audioapp_frontend' | head -1)
if [ -n "$FRONTEND_CONTAINER" ]; then
  docker exec "$FRONTEND_CONTAINER" grep -o 'main\.[^"]*\.js' /usr/share/nginx/html/index.html
fi

# Production nginx root and upload hash must match after deploy.
```

### Frontend Deployment Locations

The frontend is deployed to **TWO locations**:

| Location | Path | Purpose | URL |
|----------|------|---------|-----|
| **Docker Container** | `/usr/share/nginx/html/` (inside container) | Port 3001 access | http://82.165.221.205:3001 |
| **Main Nginx** | `/opt/audioapp/frontend/audio-waveform-visualizer/build/` | SSL production | https://audio.precisepouchtrack.com |

**Important:** The public domain `audio.precisepouchtrack.com` is served by **Main Nginx root**. If you only copy files into the Docker container, public users may still get old files.

Use this check after each deploy:

```bash
echo "Nginx root hash:" && grep -o 'main\.[^"]*\.js' /opt/audioapp/frontend/audio-waveform-visualizer/build/index.html
echo "Upload folder hash:" && grep -o 'main\.[^"]*\.js' /opt/audioapp/frontend/build/index.html
```

Both hashes should match.

### Cleanup Old Files

After successful deployment, clean up old JavaScript files:

```bash
# On server
cd /opt/audioapp/frontend/audio-waveform-visualizer/build/static/js

# List old files
ls -1 main.*.js | grep -v "main.CURRENT.js"

# Remove old files from main nginx
rm -f main.OLD.js*

# Remove from Docker container
FRONTEND_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'audioapp_frontend|_audioapp_frontend' | head -1)
docker exec "$FRONTEND_CONTAINER" sh -c 'cd /usr/share/nginx/html/static/js && rm -f main.OLD.js*'
```

---

## Full Stack Deployment (Both)

When you have both backend and frontend changes:

### Complete Workflow

#### On Windows Machine:

```powershell
# 1. Commit and push backend changes to GitHub
cd C:\Users\NickD\Documents\Github\Audio
git add .
git commit -m "Your commit message"
git push origin master

# 2. Build frontend
cd frontend\audio-waveform-visualizer
npm run build

# 3. Upload frontend to server
scp -r build\* nickd@82.165.221.205:/opt/audioapp/frontend/build/
```

#### On Server:

```bash
ssh nickd@82.165.221.205
cd /opt/audioapp

# 4. Pull backend changes
git pull origin master

# 5. Deploy frontend to both locations
rsync -av --delete --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r /opt/audioapp/frontend/build/ /opt/audioapp/frontend/audio-waveform-visualizer/build/
FRONTEND_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'audioapp_frontend|_audioapp_frontend' | head -1)
if [ -n "$FRONTEND_CONTAINER" ]; then
  docker cp /opt/audioapp/frontend/build/. $FRONTEND_CONTAINER:/usr/share/nginx/html/
  docker restart $FRONTEND_CONTAINER
fi

# Fix permissions for nginx (critical if files were uploaded via SCP)
sudo chmod -R u=rwX,go=rX /opt/audioapp/frontend/audio-waveform-visualizer/build/
sudo chown -R nickd:www-data /opt/audioapp/frontend/audio-waveform-visualizer/build/

sudo systemctl reload nginx

# 6. Restart backend services
touch backend/myproject/wsgi.py
docker restart audioapp_celery_worker

# 7. Verify deployment
echo "Frontend versions:"
echo "Nginx production root:" && grep -o 'main\.[^"]*\.js' /opt/audioapp/frontend/audio-waveform-visualizer/build/index.html
echo "Upload folder:" && grep -o 'main\.[^"]*\.js' /opt/audioapp/frontend/build/index.html

echo -e "\nBackend services:"
docker ps --filter name=audioapp
```

---

## Verification & Testing

### Pre-Deployment Checklist

- [ ] Backend changes committed and pushed to GitHub
- [ ] Frontend built successfully on local machine
- [ ] No build errors or warnings
- [ ] Git repository is clean (`git status`)

### Post-Deployment Verification

#### Backend Verification

```bash
# Check all containers are running
docker ps --filter name=audioapp

# Verify Celery worker loaded new code
docker logs --tail 50 audioapp_celery_worker | grep "ready"

# Check Django backend is responding
curl -s http://localhost:8001/api/health/

# Check recent logs for errors
docker logs --tail 100 audioapp_backend | grep -i error
docker logs --tail 100 audioapp_celery_worker | grep -i error
```

#### Frontend Verification

```bash
# Verify what the public domain should be serving (nginx root)
echo "Nginx production root:" && grep -o 'main\.[^"]*\.js' /opt/audioapp/frontend/audio-waveform-visualizer/build/index.html

# Verify uploaded build hash
echo "Upload staging folder:" && grep -o 'main\.[^"]*\.js' /opt/audioapp/frontend/build/index.html

# Optional: verify container hash for port 3001 path
FRONTEND_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'audioapp_frontend|_audioapp_frontend' | head -1)
if [ -n "$FRONTEND_CONTAINER" ]; then
  echo "Container html root:" && docker exec "$FRONTEND_CONTAINER" grep -o 'main\.[^"]*\.js' /usr/share/nginx/html/index.html
fi

# Nginx production root and upload staging hash should match after deploy.
```

#### Browser Verification

1. **Clear browser cache first!**
   - Hard refresh: `Ctrl + Shift + R` (Windows/Linux) or `Cmd + Shift + R` (Mac)
   - Or use Incognito mode: `Ctrl + Shift + N`

2. **Check in DevTools:**
   - Press `F12` → Network tab
   - Refresh page
   - Verify correct `main.HASH.js` file is loaded
   - Check for 404 errors on old files

3. **Test functionality:**
   - Test the features you changed
   - Check browser console for JavaScript errors
   - Verify API calls are working

---

## Troubleshooting

### Backend Issues

#### Celery Worker Not Running
```bash
# Check status
docker ps --filter name=audioapp_celery_worker

# Start if stopped
docker start audioapp_celery_worker

# Check logs for errors
docker logs audioapp_celery_worker
```

#### Old Code Still Running
**Symptom:** 
- Changes not taking effect after git pull
- Old parameters/values showing in UI or logs
- Errors that should be fixed are still occurring
- Code on disk is updated but behavior hasn't changed

**Diagnosis:**
```bash
# Check how long Celery has been running
docker ps --filter name=audioapp_celery_worker --format "{{.Names}}: {{.Status}}"

# If uptime is HOURS or DAYS, it's running old code!
# Example: "Up 21 hours" = code from 21 hours ago, not current!

# Verify what commit is on disk vs what's running
cd /opt/audioapp && git log --oneline -1
# This shows what's on disk

# But if Celery hasn't restarted since before that commit,
# it's still running the OLD version that was on disk when it started!
```

**Root Cause:**
Python code is loaded into memory when containers start. Git pull updates files on disk, but running processes continue using old code from memory until restarted.

**Solution:**
```bash
# Restart Celery worker to load new code
docker restart audioapp_celery_worker

# Wait a few seconds, then verify it's ready with NEW code
sleep 3
docker logs --tail 30 audioapp_celery_worker | grep "ready"

# Check the timestamp - should be very recent (seconds ago)
# Example: [2026-03-18 09:59:07,811: INFO/MainProcess] celery@abc123 ready.
```

**Prevention:**
ALWAYS check service uptime after git pull. If uptime is longer than your deployment, you forgot to restart!

#### Code on Disk But Not in Memory (COMMON MISTAKE!)
**Symptom:**
- `git pull` succeeded and shows new commit
- `git log` shows the latest commit with your fix
- Checking files on disk shows your changes are there
- But the bug/error is STILL happening!

**What Happened:**
```bash
# Git pull succeeded ✅
cd /opt/audioapp && git pull origin master
# Output: Updating abc1234..def5678

# But you forgot this! ❌
docker restart audioapp_celery_worker

# Result: New code is on DISK, but old code is in MEMORY!
```

**How to Diagnose:**
```bash
# 1. Check what commit is on disk
cd /opt/audioapp && git log --oneline -1
# Shows: ed176c4 Fix UnboundLocalError

# 2. Check when Celery started (uptime)
docker ps --filter name=audioapp_celery_worker
# Shows: Up 21 hours  <-- This is the problem!

# 3. Conclusion: Celery started 21 hours ago with OLD code
#    Even though new code is on disk, Celery hasn't loaded it!
```

**Solution:**
```bash
# Restart Celery to load code from disk into memory
docker restart audioapp_celery_worker

# Verify it restarted (uptime should be seconds)
docker ps --filter name=audioapp_celery_worker
# Should show: Up 15 seconds  <-- Good!

# Verify it's ready with new code
docker logs --tail 50 audioapp_celery_worker | grep "ready"
# Check timestamp is very recent
```

**Remember:**
- Git pull = updates files on DISK
- Docker restart = loads files from disk into MEMORY
- Python code runs from MEMORY, not disk!
- You need BOTH for changes to take effect!

#### Code on Host But Not in Container (CRITICAL ISSUE!)
**Symptom:**
- `git pull` succeeded and shows new commit
- `git log` shows the latest commit with your fix  
- Checking files **on host** shows your changes are there
- But checking files **inside container** shows OLD code!
- The bug/error is STILL happening even after restart!

**What Happened:**
Backend containers use **Dockerfiles**, not volume mounts. Code is **BAKED into the image** during build.

```
When you git pull:
  Host: /opt/audioapp/backend/tasks/duplicate_tasks.py ← NEW CODE ✅
  Container: /app/tasks/duplicate_tasks.py ← OLD CODE ❌ (baked into image)

When you docker restart:
  Container: Still uses OLD image with OLD code ❌

When you docker-compose build + up:
  - Builds new image FROM host code ✅
  - Creates new container FROM new image ✅  
  - Container now has NEW code ✅
```

**How to Diagnose:**
```bash
# 1. Check code on HOST (should be new)
grep -n \"project = None\" /opt/audioapp/backend/audioDiagnostic/tasks/duplicate_tasks.py

# 2. Check code INSIDE CONTAINER (might be old!)
docker exec audioapp_celery_worker grep -n \"project = None\" /app/audioDiagnostic/tasks/duplicate_tasks.py

# 3. If host has it but container doesn't, you forgot to rebuild!
```

**Solution:**
```bash
# Rebuild images with new code from host
cd /opt/audioapp
docker-compose -f docker-compose.production.yml up -d --build backend celery_worker

# Wait for containers to start
sleep 5

# Verify new code is in container
docker exec audioapp_celery_worker grep -n \"project = None\" /app/audioDiagnostic/tasks/duplicate_tasks.py
```

**Prevention:**
ALWAYS use `docker-compose up -d --build` after git pull, not just `docker restart`!

#### Django Not Reloading
```bash
# Force reload
touch /opt/audioapp/backend/myproject/wsgi.py

# Or restart entire backend container
docker restart audioapp_backend
```

#### Git Pull Conflicts
```bash
# Stash local changes
git stash

# Pull from remote
git pull origin master

# Reapply local changes
git stash pop

# If conflicts, resolve manually
git status
```

### Frontend Issues

#### Browser Shows Old Version
**Symptom:** UI doesn't reflect changes, old JS file loading

**Solution:**
1. **Hard refresh:** `Ctrl + Shift + R`
2. **Clear cache:** Settings → Privacy → Clear browsing data
3. **Incognito mode:** `Ctrl + Shift + N`

#### Different Versions on Port 3001 vs SSL
**Symptom:** `curl` shows different hashes for different URLs

**Solution:** Redeploy to both locations
```bash
# Deploy to main nginx
rsync -av --delete --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r /opt/audioapp/frontend/build/ /opt/audioapp/frontend/audio-waveform-visualizer/build/
chmod -R 755 /opt/audioapp/frontend/audio-waveform-visualizer/build
sudo systemctl reload nginx

# Deploy to Docker container
docker cp /opt/audioapp/frontend/build/. audioapp_frontend:/usr/share/nginx/html/
docker restart audioapp_frontend
```

#### Build Fails on Windows
**Symptom:** `npm run build` errors

**Common fixes:**
```powershell
# Clear node_modules and reinstall
Remove-Item -Recurse -Force node_modules
npm install

# Clear npm cache
npm cache clean --force

# Try building again
npm run build
```

#### SCP Upload Fails
**Symptom:** "Connection closed" or permission denied

**Solution:**
- Check password is correct
- Verify ssh access: `ssh nickd@82.165.221.205`
- Check server disk space: `df -h`

---

## Quick Reference Commands

### Backend Quick Deploy (CORRECT METHOD)

**⚠️ OLD METHOD DOES NOT WORK - Code is baked into images!**
```bash
# ❌ THIS DOES NOT WORK - Only restarts containers with old code
cd /opt/audioapp && git pull && docker restart audioapp_celery_worker
```

**✅ CORRECT METHOD - Rebuild images:**
```bash
# Pull code and rebuild images with new code
cd /opt/audioapp && \
git pull origin master && \
docker-compose -f docker-compose.production.yml up -d --build backend celery_worker && \
echo "✅ Deployment complete. Verifying..." && \
sleep 5 && \
docker ps --filter name=audioapp_celery_worker --format "Celery: {{.Status}}" && \
docker logs --tail 20 audioapp_celery_worker | grep "ready" | tail -1
```

**After deploying, verify Celery uptime is SECONDS, not HOURS!**

### Backend Quick Deploy + Verify
```bash
# Deploy: Pull + Rebuild + Recreate
cd /opt/audioapp && \
git pull origin master && \
docker-compose -f docker-compose.production.yml up -d --build backend celery_worker

# Verify services rebuilt (wait for Celery to start)
sleep 5 && echo "=== Verification ===" && \
echo "Celery uptime (should be < 1 minute):" && \
docker ps --filter name=audioapp_celery_worker --format "{{.Status}}" && \
echo "" && echo "Celery ready status:" && \
docker logs --tail 30 audioapp_celery_worker | grep "ready" | tail -1 && \
echo "" && echo "Git commit on host:" && \
git log --oneline -1
```

### Frontend Quick Deploy (from Windows)
```powershell
# Build + Upload + Deploy
cd C:\Users\NickD\Documents\Github\Audio\frontend\audio-waveform-visualizer
npm run build
scp -r build\* nickd@82.165.221.205:/opt/audioapp/frontend/build/
ssh nickd@82.165.221.205 "FRONTEND_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'audioapp_frontend|_audioapp_frontend' | head -1) && rsync -av --delete --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r /opt/audioapp/frontend/build/ /opt/audioapp/frontend/audio-waveform-visualizer/build/ && if [ -n \"$FRONTEND_CONTAINER\" ]; then docker cp /opt/audioapp/frontend/build/. $FRONTEND_CONTAINER:/usr/share/nginx/html/ && docker restart $FRONTEND_CONTAINER; fi && sudo systemctl reload nginx"
```

### Check Deployed Versions
```bash
# Backend services uptime
docker ps --filter name=audioapp --format "{{.Names}}: {{.Status}}"

# Frontend versions
echo "Port 3001: $(curl -s http://localhost:3001/ | grep -o 'main\.[^"]*\.js')"
echo "SSL: $(curl -s https://audio.precisepouchtrack.com/ | grep -o 'main\.[^"]*\.js')"
```

### View Logs
```bash
# Django backend
docker logs --tail 100 audioapp_backend

# Celery worker
docker logs --tail 100 audioapp_celery_worker

# Nginx (main server)
sudo tail -100 /var/log/nginx/error.log
sudo tail -100 /var/log/nginx/access.log
```

---

## Important Notes

### Backend Code is BAKED Into Docker Images (MOST CRITICAL!)
**⚠️ CRITICAL:** Backend code is **built into Docker images**, NOT volume-mounted!

**What This Means:**
- `git pull` only updates files **on the host** at `/opt/audioapp/backend/`
- Docker containers have code **baked into the image** at `/app/`
- Containers will continue using **old code from the old image** until you rebuild!

**Correct Deployment Process:**
1. **Git pull** \u2192 Updates host: `/opt/audioapp/backend/` \u2705
2. **Docker rebuild** \u2192 Copies host code into new image \u2705
3. **Docker up** \u2192 Creates containers from new image \u2705
4. Containers now have new code! \u2705

**Wrong Process (CODE STAYS OLD!):**
1. **Git pull** \u2192 Updates host \u2705
2. **Docker restart** \u2192 Restarts containers with OLD image \u274c
3. Code on host is new, but containers still use old image! \u274c
4. Bug persists even though fix is on disk! \u274c

**Commands:**
- \u274c **WRONG:** `docker restart audioapp_celery_worker` (uses old image)
- \u274c **WRONG:** `touch backend/myproject/wsgi.py` (only works for volume-mounted code)
- \u2705 **CORRECT:** `docker-compose up -d --build backend celery_worker` (rebuilds image)

**Real Example of This Problem:**
```bash
# Day 1: Deploy fix for UnboundLocalError
git pull origin master  # ✅ Code on disk updated
# Forgot to restart! ❌

# Day 2: Bug still happening!
# Check logs: Still shows UnboundLocalError
# Check code: File shows fix is there
# Check Celery uptime: "Up 21 hours" ← Running OLD code from 21 hours ago!

# Solution:
docker restart audioapp_celery_worker  # ✅ Now loads NEW code from disk
# Bug fixed!
```

**How to Prevent:**
1. After `git pull`, IMMEDIATELY run: `docker ps --filter name=audioapp_celery_worker`
2. Note the current uptime (e.g., "Up 21 hours")
3. Restart: `docker restart audioapp_celery_worker`
4. Check again: Should show "Up 5 seconds"
5. If uptime didn't reset, you didn't actually restart!

### Frontend Must Be Built on Windows
**⚠️ Critical:** The server has Node.js v12.22.9 which is too old to build modern React apps. Always build on your Windows machine (which has a current Node.js version) and upload only the build artifacts.

Never try to run `npm install` or `npm run build` on the server!

### Dual Nginx Deployment
**⚠️ Critical:** The frontend is served by TWO nginx servers:
1. Docker container nginx (port 3001)
2. Main nginx with SSL (production domain)

Both must be updated for consistent deployment. The deploy commands handle this automatically.

### Git Workflow
- Backend code managed in Git repository
- Frontend source code in Git repository
- Frontend **build artifacts** NOT in Git (locally built)
- Pull backend from Git, build frontend locally

---

## Server Details

### Production URLs
- **Public (SSL):** https://audio.precisepouchtrack.com
- **Docker (HTTP):** http://82.165.221.205:3001
- **Backend API:** http://localhost:8001 (internal only)

### Key Directories
```
/opt/audioapp/
├── backend/                           # Django + Celery backend
│   ├── audioDiagnostic/
│   │   ├── tasks/                     # Celery tasks (requires worker restart)
│   │   ├── views/                     # Django views (requires wsgi.py touch)
│   │   └── models.py
│   └── myproject/
│       ├── settings.py                # Django settings
│       └── wsgi.py                    # Touch to reload Django
├── frontend/
│   ├── build/                         # Upload destination (scp target)
│   └── audio-waveform-visualizer/
│       └── build/                     # Main nginx serves from here
├── docker-compose.production.yml      # Docker services config
└── .git/                              # Git repository
```

### Docker Containers
```
audioapp_frontend          # Nginx serving frontend (port 3001)
audioapp_backend           # Django backend (port 8001)
audioapp_celery_worker     # Celery worker (tasks)
audioapp_db                # PostgreSQL database
audioapp_redis             # Redis (Celery broker)
```

---

## Deployment Checklist

Use this checklist for each deployment:

### Backend Only
- [ ] Commit and push changes to GitHub
- [ ] SSH to server: `ssh nickd@82.165.221.205`
- [ ] Pull changes: `git pull origin master`
- [ ] Reload Django: `touch backend/myproject/wsgi.py`
- [ ] Restart Celery: `docker restart audioapp_celery_worker`
- [ ] Verify services running: `docker ps`
- [ ] Check logs for errors
- [ ] Test changed functionality

### Frontend Only
- [ ] Build on Windows: `npm run build`
- [ ] Upload to server: `scp -r build\* nickd@82.165.221.205:/opt/audioapp/frontend/build/`
- [ ] Deploy to main nginx: `rsync + chmod + reload`
- [ ] Deploy to Docker container: `docker cp + restart`
- [ ] Verify both URLs serve same version
- [ ] Hard refresh browser
- [ ] Test UI changes

### Full Stack
- [ ] Follow backend checklist above
- [ ] Follow frontend checklist above
- [ ] Verify frontend can communicate with backend
- [ ] Test end-to-end functionality
- [ ] Monitor logs for errors

---

**Last Updated:** March 17, 2026
**Server:** 82.165.221.205
**Domain:** https://audio.precisepouchtrack.com
