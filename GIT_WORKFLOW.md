# Git Workflow Guide - Audio App

**Date:** February 28, 2026  
**Repository:** /opt/audioapp  
**Branch:** master

---

## 📤 **Push Changes from Server to GitHub**

### Step 1: Add All Changes

```bash
cd /opt/audioapp

# Add all modified files and new files
git add -A

# Or add specific files:
git add SERVER_DEPLOYMENT_GUIDE.md
git add TROUBLESHOOTING_LOGIN_ISSUE.md
git add backend/myproject/settings.py
git add backend/accounts/views.py
git add docker-compose.production.yml
git add backend/.env.production
git add frontend/audio-waveform-visualizer/.env.production
```

### Step 2: Check What Will Be Committed

```bash
git status
```

### Step 3: Commit Changes

```bash
git commit -m "Fix login issues and add deployment documentation

- Fixed ALLOWED_HOSTS to read from environment
- Fixed CustomAuthToken to allow anonymous access
- Fixed subscription access with get_or_create
- Added comprehensive deployment and troubleshooting docs
- Added docker-compose production configuration
- Updated frontend with client-side processing
- Updated backend dependencies
"
```

### Step 4: Push to GitHub

```bash
# If you need to set your git credentials first:
git config user.name "Nick D"
git config user.email "your-email@example.com"

# Push to master branch
git push origin master

# If it asks for login credentials and you have 2FA enabled,
# you'll need a Personal Access Token instead of password
# Generate one at: https://github.com/settings/tokens
```

---

## 📥 **Pull Changes on Local Machine**

### Option 1: Using VSCode

1. **Open Source Control Panel:**
   - Click the Source Control icon (looks like branching icon on left sidebar)
   - Or press: `Ctrl+Shift+G` (Windows/Linux) or `Cmd+Shift+G` (Mac)

2. **If Repository Not Detected:**
   ```
   File → Open Folder → Navigate to your local audio app folder
   ```

3. **Pull Changes:**
   - Click the `...` menu (three dots) in Source Control panel
   - Select: `Pull` or `Pull from...`
   - Choose: `origin/master`

4. **If Git Not Initialized:**
   - Open Terminal in VSCode: `` Ctrl+` `` (backtick)
   - Run:
     ```bash
     git init
     git remote add origin YOUR_REPO_URL
     git fetch origin
     git checkout master
     git pull origin master
     ```

### Option 2: Using Terminal/Command Line

```bash
# Navigate to your local project folder
cd /path/to/your/local/audio-app

# Check current status
git status

# Pull latest changes
git pull origin master

# If repository not initialized:
git init
git remote add origin YOUR_REPO_URL
git pull origin master
```

### Option 3: Fresh Clone (If Local Repo Has Issues)

```bash
# Go to parent directory
cd /where/you/want/to/clone

# Clone the repository fresh
git clone YOUR_REPO_URL audio-app

# Navigate into it
cd audio-app
```

---

## 🔍 **Troubleshooting VSCode Git Issues**

### Issue: "VSCode not finding git repository"

**Solution 1: Initialize Git in VSCode**
```
1. Open Command Palette: Ctrl+Shift+P (Windows/Linux) or Cmd+Shift+P (Mac)
2. Type: "Git: Initialize Repository"
3. Select your project folder
```

**Solution 2: Open Correct Folder**
```
File → Open Folder → Select the ROOT folder of your project
(The folder that contains .git directory)
```

**Solution 3: Check Git is Installed**
```
Open VSCode Terminal (Ctrl+`)
Run: git --version
If not found, install git:
- Windows: https://git-scm.com/download/win
- Mac: brew install git
- Linux: sudo apt install git
```

**Solution 4: Reload VSCode**
```
Ctrl+Shift+P → "Developer: Reload Window"
```

**Solution 5: Check Git Extension is Enabled**
```
1. Go to Extensions (Ctrl+Shift+X)
2. Search for "Git"
3. Ensure "Git" extension is enabled (not disabled)
```

---

## 🔑 **Setting Up Git Credentials**

### For HTTPS Cloning:

```bash
# Set your name and email
git config --global user.name "Nick D"
git config --global user.email "your-email@example.com"

# If you have 2FA, create a Personal Access Token:
# 1. Go to: https://github.com/settings/tokens
# 2. Click "Generate new token (classic)"
# 3. Select scopes: repo (all), workflow
# 4. Copy the token
# 5. Use token as password when git asks
```

### For SSH Cloning (Recommended):

```bash
# Generate SSH key if you don't have one
ssh-keygen -t ed25519 -C "your-email@example.com"

# Copy public key
cat ~/.ssh/id_ed25519.pub

# Add to GitHub:
# 1. Go to: https://github.com/settings/keys
# 2. Click "New SSH key"
# 3. Paste the public key
# 4. Save

# Test connection
ssh -T git@github.com

# Change remote to SSH
git remote set-url origin git@github.com:USERNAME/REPO.git
```

---

## 📋 **Current Changes to Push (Feb 28, 2026)**

### Documentation Files (New):
- ✅ `SERVER_DEPLOYMENT_GUIDE.md` - Complete deployment guide with all commands
- ✅ `TROUBLESHOOTING_LOGIN_ISSUE.md` - Login troubleshooting documentation
- ✅ `CLIENT_SIDE_PROCESSING.md` - Client-side processing documentation
- ✅ `SERVER_MAINTENANCE_TODO.md` - Maintenance TODO list
- ✅ `GIT_WORKFLOW.md` - This file

### Backend Files (Modified):
- ✅ `backend/myproject/settings.py` - Fixed ALLOWED_HOSTS to read from env
- ✅ `backend/accounts/views.py` - Fixed CustomAuthToken permissions
- ✅ `backend/accounts/urls.py` - Updated URL routing
- ✅ `backend/requirements.txt` - Updated dependencies

### Docker Files (New):
- ✅ `docker-compose.production.yml` - Production docker compose
- ✅ `backend/.env.production` - Backend environment variables
- ✅ `backend/Dockerfile.production` - Backend production Dockerfile
- ✅ `backend/docker-entrypoint.sh` - Backend entrypoint script
- ✅ `backend/docker-entrypoint-celery.sh` - Celery entrypoint
- ✅ `frontend/audio-waveform-visualizer/.env.production` - Frontend env
- ✅ `frontend/audio-waveform-visualizer/Dockerfile.production` - Frontend Dockerfile
- ✅ `frontend/audio-waveform-visualizer/nginx.conf` - Nginx config

### Frontend Files (Modified):
- ✅ `frontend/audio-waveform-visualizer/package.json` - Added dependencies
- ✅ `frontend/audio-waveform-visualizer/package-lock.json` - Locked versions
- ✅ `frontend/audio-waveform-visualizer/src/components/Auth/*.js` - Auth fixes
- ✅ `frontend/audio-waveform-visualizer/src/components/ProjectTabs/Tab1Files.js` - Client-side processing
- ✅ `frontend/audio-waveform-visualizer/src/screens/*.js` - Updated screens
- ✅ `frontend/audio-waveform-visualizer/src/services/` - New services folder

---

## 🚀 **Complete Workflow Commands**

### On Server:

```bash
cd /opt/audioapp

# 1. Check what's changed
git status

# 2. Add everything
git add -A

# 3. Commit
git commit -m "Fix login issues and add deployment documentation

- Fixed ALLOWED_HOSTS to read from environment
- Fixed CustomAuthToken to allow anonymous access
- Fixed subscription access with get_or_create
- Added comprehensive deployment and troubleshooting docs
- Added docker-compose production configuration
- Updated frontend with client-side processing
- Updated backend dependencies
"

# 4. Push
git push origin master
```

### On Local Machine (VSCode):

```bash
# Option A: Using VSCode UI
# 1. Open Source Control (Ctrl+Shift+G)
# 2. Click ... menu → Pull

# Option B: Using Terminal
cd /path/to/your/local/audio-app
git pull origin master

# Option C: Fresh clone if nothing works
cd /where/you/want/project
git clone YOUR_REPOSITORY_URL
cd audio-app
```

---

## ⚠️ **Important Notes**

### Files to Exclude from Git:

The following files should NOT be committed (already in .gitignore):
- `*.pyc` - Python compiled files
- `__pycache__/` - Python cache directories
- `node_modules/` - Node dependencies
- `*.sqlite3` - Local database files
- `*.log` - Log files
- `pouchtrackenv/` - Virtual environment

### Sensitive Files:

If you accidentally committed `.env.production` with passwords:
1. Remove sensitive values from file in repo
2. Use environment variables on server instead
3. Update .gitignore to exclude `.env.*` files
4. Use `.env.example` template in repo instead

### Before Pulling on Local Machine:

```bash
# Stash any local changes first
git stash

# Pull from server
git pull origin master

# Re-apply your local changes
git stash pop
```

---

## 🔗 **Common Git Commands**

```bash
# Check status
git status

# See what changed
git diff

# See commit history
git log --oneline -10

# Undo last commit (keep changes)
git reset --soft HEAD~1

# Discard all local changes
git reset --hard origin/master

# Create new branch
git checkout -b feature-name

# Switch branch
git checkout master

# Merge branch
git merge feature-name

# Pull latest
git pull origin master

# Push changes
git push origin master
```

---

## ✅ **Verification Steps**

After pushing from server and pulling on local:

### On Server:
```bash
cd /opt/audioapp
git log -1  # Should show your latest commit
git status  # Should show "nothing to commit, working tree clean"
```

### On Local:
```bash
cd /path/to/local/audio-app
git log -1  # Should match server commit
git status  # Should show same state

# Verify files exist
ls -la SERVER_DEPLOYMENT_GUIDE.md
ls -la TROUBLESHOOTING_LOGIN_ISSUE.md
ls -la docker-compose.production.yml
```

---

**Repository URL:** (Replace with your actual GitHub repo URL)

**Need Help?** 
- GitHub Docs: https://docs.github.com/en/get-started
- VSCode Git: https://code.visualstudio.com/docs/editor/versioncontrol
- Git Guide: https://git-scm.com/book/en/v2
