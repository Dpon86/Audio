# Audio App Deployment Plan

Quick reference deployment workflow for frontend and backend updates.

---

## Frontend Deployment Workflow

### What You Do on Windows Machine

#### Step 1: Build the React App
```powershell
# Navigate to project
cd C:\Users\NickD\Documents\Github\Audio\frontend\audio-waveform-visualizer

# Build production bundle
npm run build
```

**Expected Output:**
```
File sizes after gzip:
  360.xx kB  build\static\js\main.HASH.js
  27.57 kB   build\static\css\main.HASH.css
```

#### Step 2: Upload Build Files to Server
```powershell
# Upload entire build directory
scp -r build\* nickd@82.165.221.205:/opt/audioapp/frontend/build/
```

**What This Does:**
- Uploads: `index.html`, `asset-manifest.json`, `static/js/main.HASH.js`, `static/css/main.HASH.css`
- Destination on server: `/opt/audioapp/frontend/build/`

#### Step 3: Deploy to Docker Container
```powershell
# Copy files to Docker nginx container
ssh nickd@82.165.221.205 "docker cp /opt/audioapp/frontend/build/. audioapp_frontend:/usr/share/nginx/html/ && docker restart audioapp_frontend"
```

**What This Does:**
- Copies files from `/opt/audioapp/frontend/build/` → Inside Docker container at `/usr/share/nginx/html/`
- Restarts Docker container to apply changes
- Makes frontend available at: `http://82.165.221.205:3001`

### What Needs to Be Done on Server

SSH to server and run these commands:

```bash
ssh nickd@82.165.221.205
cd /opt/audioapp
```

#### Step 4: Deploy to Main Nginx (SSL Production)
```bash
# Copy to main nginx location
rsync -av --delete /opt/audioapp/frontend/build/ /opt/audioapp/frontend/audio-waveform-visualizer/build/

# Fix permissions for nginx
chmod -R 755 /opt/audioapp/frontend/audio-waveform-visualizer/build

# Reload nginx to serve new files
sudo systemctl reload nginx
```

**What This Does:**
- Copies files from upload directory → Main nginx root at `/opt/audioapp/frontend/audio-waveform-visualizer/build/`
- Sets correct permissions (755) so nginx can serve files
- Reloads nginx configuration
- Makes frontend available at: `https://audio.precisepouchtrack.com`

#### Step 5: Verify Deployment
```bash
# Check both URLs serve same version
curl -s http://localhost:3001/ | grep -o 'main\.[^"]*\.js'
curl -s https://audio.precisepouchtrack.com/ | grep -o 'main\.[^"]*\.js'

# Both should show same hash!
```

#### Step 6: Clean Up Old Files (Optional)
```bash
cd /opt/audioapp/frontend/audio-waveform-visualizer/build/static/js

# List old files
ls -1 main.*.js | grep -v "main.CURRENT_HASH.js"

# Remove from main nginx
rm -f main.OLD_HASH.js*

# Remove from Docker container
docker exec audioapp_frontend sh -c 'cd /usr/share/nginx/html/static/js && rm -f main.OLD_HASH.js*'
```

### Frontend File Destinations

| Build Files | Destination 1 (Docker) | Destination 2 (Main Nginx) |
|-------------|------------------------|----------------------------|
| `build/index.html` | `/usr/share/nginx/html/index.html` | `/opt/audioapp/frontend/audio-waveform-visualizer/build/index.html` |
| `build/static/js/main.HASH.js` | `/usr/share/nginx/html/static/js/main.HASH.js` | `/opt/audioapp/frontend/audio-waveform-visualizer/build/static/js/main.HASH.js` |
| `build/static/css/main.HASH.css` | `/usr/share/nginx/html/static/css/main.HASH.css` | `/opt/audioapp/frontend/audio-waveform-visualizer/build/static/css/main.HASH.css` |

**⚠️ IMPORTANT:** Both destinations must be updated for complete deployment!

### One-Liner Frontend Deploy (From Windows)

After uploading with scp, run this single command:

```powershell
ssh nickd@82.165.221.205 "rsync -av --delete /opt/audioapp/frontend/build/ /opt/audioapp/frontend/audio-waveform-visualizer/build/ && chmod -R 755 /opt/audioapp/frontend/audio-waveform-visualizer/build && docker cp /opt/audioapp/frontend/build/. audioapp_frontend:/usr/share/nginx/html/ && docker restart audioapp_frontend && sudo systemctl reload nginx"
```

---

## Backend Deployment Workflow (GitHub)

### What You Do on Windows Machine

#### Step 1: Commit Changes to Git
```powershell
cd C:\Users\NickD\Documents\Github\Audio

# Check what changed
git status

# Add all changes
git add .

# Commit with descriptive message
git commit -m "Description of changes (e.g., Updated duplicate detection parameters)"

# Push to GitHub
git push origin master
```

**What This Does:**
- Saves your backend code changes to Git
- Pushes changes to GitHub repository
- Makes changes available for server to pull

### What Needs to Be Done on Server

SSH to server and run these commands:

```bash
ssh nickd@82.165.221.205
cd /opt/audioapp
```

#### Step 2: Pull Changes from GitHub
```bash
# Check what's available
git fetch origin
git log --oneline HEAD..origin/master

# Pull latest changes
git pull origin master
```

**What This Does:**
- Downloads latest backend code from GitHub
- Updates files in `/opt/audioapp/backend/`
- **IMPORTANT:** Code is on disk but NOT loaded into memory yet!

#### Step 3: Restart Backend Services

**⚠️ CRITICAL:** Backend code runs in memory. You MUST restart services!

##### For Celery Task Changes:
```bash
docker restart audioapp_celery_worker

# Verify it restarted
docker ps --filter name=audioapp_celery_worker --format "{{.Names}}: {{.Status}}"

# Check logs
docker logs --tail 30 audioapp_celery_worker | grep "ready"
```

**Restart Celery for:**
- Changes to `backend/audioDiagnostic/tasks/*.py`
- Any file in `tasks/` directory (duplicate_tasks.py, transcription_tasks.py, etc.)

##### For Django View/Model/Serializer Changes:
```bash
touch backend/myproject/wsgi.py

# Django auto-reloads when wsgi.py timestamp changes
```

**Touch wsgi.py for:**
- Changes to `backend/audioDiagnostic/views/*.py`
- Changes to `backend/audioDiagnostic/models.py`
- Changes to `backend/api/Serializers/*.py`
- Changes to `backend/api/urls.py`

##### For Settings Changes:
```bash
# Reload both!
touch backend/myproject/wsgi.py
docker restart audioapp_celery_worker
```

**Restart both for:**
- Changes to `backend/myproject/settings.py`

#### Step 4: Verify Backend Deployment
```bash
# Check all containers running
docker ps --filter name=audioapp

# Check Celery loaded new code
docker logs --tail 50 audioapp_celery_worker | grep "ready"

# Check for errors
docker logs --tail 100 audioapp_celery_worker | grep -i error
docker logs --tail 100 audioapp_backend | grep -i error
```

### Backend File Locations & Restart Requirements

| File Type | Path | What to Restart |
|-----------|------|-----------------|
| **Celery Tasks** | `/opt/audioapp/backend/audioDiagnostic/tasks/duplicate_tasks.py` | `docker restart audioapp_celery_worker` |
| | `/opt/audioapp/backend/audioDiagnostic/tasks/transcription_tasks.py` | `docker restart audioapp_celery_worker` |
| | `/opt/audioapp/backend/audioDiagnostic/tasks/*.py` | `docker restart audioapp_celery_worker` |
| **Django Views** | `/opt/audioapp/backend/audioDiagnostic/views/*.py` | `touch backend/myproject/wsgi.py` |
| | `/opt/audioapp/backend/audioDiagnostic/Views/*.py` | `touch backend/myproject/wsgi.py` |
| **Django Models** | `/opt/audioapp/backend/audioDiagnostic/models.py` | `touch backend/myproject/wsgi.py` |
| **Serializers** | `/opt/audioapp/backend/api/Serializers/*.py` | `touch backend/myproject/wsgi.py` |
| **URLs** | `/opt/audioapp/backend/api/urls.py` | `touch backend/myproject/wsgi.py` |
| **Settings** | `/opt/audioapp/backend/myproject/settings.py` | Both: `touch wsgi.py` + `docker restart celery` |

### One-Liner Backend Deploy (From Server)

```bash
cd /opt/audioapp && git pull origin master && touch backend/myproject/wsgi.py && docker restart audioapp_celery_worker
```

---

## Full Stack Deployment (Frontend + Backend)

When you have both frontend and backend changes:

### Complete Workflow

#### On Windows Machine:

```powershell
# 1. Commit backend to Git
cd C:\Users\NickD\Documents\Github\Audio
git add .
git commit -m "Your changes description"
git push origin master

# 2. Build frontend
cd frontend\audio-waveform-visualizer
npm run build

# 3. Upload frontend
scp -r build\* nickd@82.165.221.205:/opt/audioapp/frontend/build/

# 4. Deploy Docker container
ssh nickd@82.165.221.205 "docker cp /opt/audioapp/frontend/build/. audioapp_frontend:/usr/share/nginx/html/ && docker restart audioapp_frontend"
```

#### On Server:

```bash
ssh nickd@82.165.221.205
cd /opt/audioapp

# 5. Pull backend from GitHub
git pull origin master

# 6. Deploy frontend to main nginx
rsync -av --delete /opt/audioapp/frontend/build/ /opt/audioapp/frontend/audio-waveform-visualizer/build/
chmod -R 755 /opt/audioapp/frontend/audio-waveform-visualizer/build/
sudo systemctl reload nginx

# 7. Restart backend services
touch backend/myproject/wsgi.py
docker restart audioapp_celery_worker

# 8. Verify everything
echo "Frontend versions:"
curl -s http://localhost:3001/ | grep -o 'main\.[^"]*\.js'
curl -s https://audio.precisepouchtrack.com/ | grep -o 'main\.[^"]*\.js'

echo "Backend services:"
docker ps --filter name=audioapp
```

---

## Deployment Checklist

### Frontend Deployment Checklist
- [ ] Build on Windows: `npm run build`
- [ ] Upload to server: `scp -r build\* nickd@82.165.221.205:/opt/audioapp/frontend/build/`
- [ ] Deploy to Docker: `docker cp` + `docker restart audioapp_frontend`
- [ ] Deploy to main nginx: `rsync` + `chmod 755` + `sudo systemctl reload nginx`
- [ ] Verify both URLs: `curl` both locations
- [ ] Test in browser with hard refresh (`Ctrl + Shift + R`)

### Backend Deployment Checklist
- [ ] Commit changes: `git add .` + `git commit` + `git push`
- [ ] SSH to server: `ssh nickd@82.165.221.205`
- [ ] Pull changes: `git pull origin master`
- [ ] Restart Celery (if tasks changed): `docker restart audioapp_celery_worker`
- [ ] Reload Django (if views/models changed): `touch backend/myproject/wsgi.py`
- [ ] Verify services: `docker ps` + `docker logs`
- [ ] Test functionality

---

## Why This Workflow?

### Frontend (Build Locally, Upload Artifacts)
- **Why build on Windows?** Server has Node.js v12.22.9 (too old for modern React)
- **Why two nginx locations?** 
  - Docker container serves port 3001 (direct access)
  - Main nginx serves SSL domain (production with HTTPS)
- **Why upload build files?** Only compiled artifacts needed, not source code

### Backend (GitHub Pull)
- **Why use GitHub?** Version control, change history, easy rollback
- **Why restart services?** Python code loads into memory at startup
- **Why touch wsgi.py?** Signals Django to reload without full restart
- **Why restart Celery container?** Tasks run in separate worker process

---

## Quick Reference

### Frontend Destinations
```
Windows Build → Upload → Server Locations
build/        → scp →   /opt/audioapp/frontend/build/
                      ↓
                      ├─→ Docker: /usr/share/nginx/html/
                      └─→ Main nginx: /opt/audioapp/frontend/audio-waveform-visualizer/build/
```

### Backend Flow
```
Windows Code → GitHub → Server
Changes      → push →  git pull → Restart Services
                                  ├─→ Celery: docker restart
                                  └─→ Django: touch wsgi.py
```

---

## Common Commands Reference

### Check Deployed Versions
```bash
# Frontend
curl -s http://localhost:3001/ | grep -o 'main\.[^"]*\.js'
curl -s https://audio.precisepouchtrack.com/ | grep -o 'main\.[^"]*\.js'

# Backend
docker ps --filter name=audioapp --format "{{.Names}}: {{.Status}}"
```

### View Logs
```bash
docker logs --tail 100 audioapp_backend
docker logs --tail 100 audioapp_celery_worker
sudo tail -100 /var/log/nginx/error.log
```

### Clean Up Old Files
```bash
# List old frontend builds
ls -1 /opt/audioapp/frontend/audio-waveform-visualizer/build/static/js/main.*.js

# Remove specific old version
rm -f /opt/audioapp/frontend/audio-waveform-visualizer/build/static/js/main.OLD.js*
docker exec audioapp_frontend sh -c 'cd /usr/share/nginx/html/static/js && rm -f main.OLD.js*'
```

---

**Created:** March 17, 2026  
**Server:** 82.165.221.205  
**Production URL:** https://audio.precisepouchtrack.com  
**Git Repository:** https://github.com/Dpon86/Audio
