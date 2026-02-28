# Audio App Server Deployment & Maintenance Guide

**Server:** 82.165.221.205 (Ubuntu 22.04.2 LTS)  
**Domain:** https://audio.precisepouchtrack.com  
**Last Updated:** February 28, 2026

---

## 🚨 **CRITICAL FIXES - Apply After Every Server Restart**

### 1. Backend Settings Fix (REQUIRED)

The backend settings.py gets reset on restart and needs to be re-applied:

```bash
cd /opt/audioapp

# Copy fixed settings to backend container
sudo docker cp backend/myproject/settings.py audioapp_backend:/app/myproject/settings.py
sudo docker cp backend/accounts/views.py audioapp_backend:/app/accounts/views.py

# Restart backend to apply changes
docker compose -f docker-compose.production.yml restart backend

# Wait for backend to start
sleep 10

# Test login API
curl -s https://audio.precisepouchtrack.com/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"audioadmin123"}'
```

**Expected Result:** Should return `{"token": "...", "user": {...}, "subscription": {...}}`

---

### 2. Stop Celery Worker (Frees 432MB RAM)

```bash
cd /opt/audioapp
docker compose -f docker-compose.production.yml stop celery_worker

# Or remove permanently:
docker compose -f docker-compose.production.yml rm -sf celery_worker
```

---

### 3. Add Swap Space (Prevents OOM Crashes)

**Only needs to be done once, but check after restart:**

```bash
# Check if swap exists
swapon --show

# If no swap, create 4GB swap file
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make it permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Verify
free -h
```

---

## 📋 **QUICK FIX SCRIPT**

Create a script to apply all fixes automatically:

```bash
# Create the script
cat > /opt/audioapp/fix-after-restart.sh << 'EOF'
#!/bin/bash
set -e

echo "🔧 Applying post-restart fixes..."

# 1. Stop Celery worker (frees memory)
echo "Stopping Celery worker..."
cd /opt/audioapp
docker compose -f docker-compose.production.yml stop celery_worker 2>/dev/null || true

# 2. Copy backend fixes
echo "Copying backend fixes..."
sudo docker cp backend/myproject/settings.py audioapp_backend:/app/myproject/settings.py
sudo docker cp backend/accounts/views.py audioapp_backend:/app/accounts/views.py

# 3. Restart backend
echo "Restarting backend..."
docker compose -f docker-compose.production.yml restart backend

# Wait for backend to start
echo "Waiting for backend to start..."
sleep 15

# 4. Test login
echo "Testing login API..."
RESPONSE=$(curl -s https://audio.precisepouchtrack.com/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"audioadmin123"}')

if echo "$RESPONSE" | grep -q "token"; then
    echo "✅ Login API working!"
else
    echo "❌ Login API failed. Response: $RESPONSE"
fi

# 5. Check swap
echo "Checking swap space..."
if [ $(swapon --show | wc -l) -eq 0 ]; then
    echo "⚠️  No swap space! Run: sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile"
else
    echo "✅ Swap space active"
fi

echo ""
echo "✨ Fixes applied! Now hard refresh your browser: Ctrl+Shift+R"
echo "📊 Memory status:"
free -h
EOF

# Make executable
chmod +x /opt/audioapp/fix-after-restart.sh

# Run it
/opt/audioapp/fix-after-restart.sh
```

---

## 🖥️ **Memory Management**

### Current Server Specs:
- **Total RAM:** 3.8GB
- **Swap:** 4GB (after adding)
- **Available for apps:** ~1GB (rest used by system, Docker, etc.)

### Container Memory Usage:
- Backend: ~120MB (1 worker)
- Celery: ~432MB (**STOP THIS - not needed**)
- Database: ~30MB
- Redis: ~7MB
- Frontend: ~5MB

### ⚠️ **IMPORTANT LIMITATIONS:**

**DO NOT build frontend on this server:**
```bash
# ❌ THIS WILL CRASH THE SERVER:
docker compose -f docker-compose.production.yml build frontend

# Reason: npm build needs 1-2GB RAM, server only has 3.8GB total
```

**To update frontend:**
1. Build on your local machine (with more RAM)
2. Copy built files to server
3. OR add 4GB swap and accept 30+ minute build time

---

## 🌐 **Frontend Build Process (Local Machine Only)**

### Option 1: Build Locally, Deploy Built Files

```bash
# On your LOCAL machine:
cd /path/to/audio-waveform-visualizer
npm install
npm run build

# Copy built files to server:
scp -r build/* nickd@82.165.221.205:/opt/audioapp/frontend/audio-waveform-visualizer/build/

# On server - restart frontend:
cd /opt/audioapp
docker compose -f docker-compose.production.yml restart frontend
```

### Option 2: Build on Server (WITH SWAP - SLOW)

```bash
# First ensure swap is active (4GB minimum)
swapon --show

# Then build (takes 30-60 minutes with swap):
cd /opt/audioapp
docker compose -f docker-compose.production.yml build frontend
docker compose -f docker-compose.production.yml up -d frontend
```

---

## 🔐 **Authentication & User Management**

### Default Admin Account:
- **Username:** admin
- **Password:** audioadmin123
- **⚠️ CHANGE THIS PASSWORD IN PRODUCTION**

### Other Users:
- Nick (superuser)
- unlimited_user (Nick Deane)
- testuser

### Change Admin Password:

```bash
docker exec -it audioapp_backend python manage.py changepassword admin
```

---

## 🐛 **Common Issues & Solutions**

### Issue 1: "502 Bad Gateway" on File Upload

**Cause:** Out of memory - backend worker killed by OOM

**Solution:**
```bash
# Free memory by stopping Celery
docker compose -f /opt/audioapp/docker-compose.production.yml stop celery_worker

# Check memory
free -h

# Client-side processing alternative:
# Navigate to: https://audio.precisepouchtrack.com/AudioUpload
# Toggle "Process on My Device" before uploading
```

---

### Issue 2: Login Shows "Network Error"

**Cause:** Browser cached old JavaScript with localhost URLs

**Solution:**
```bash
# 1. Hard refresh browser
# Windows/Linux: Ctrl + Shift + R
# Mac: Cmd + Shift + R

# 2. Re-apply backend fixes
/opt/audioapp/fix-after-restart.sh

# 3. Clear browser cache completely or use Incognito mode
```

---

### Issue 3: Backend Settings Reset After Restart

**Cause:** Docker containers are ephemeral - changes inside containers are lost on restart

**Solution:**
```bash
# Always keep source files updated in /opt/audioapp/backend/
# After restart, re-copy to container:
sudo docker cp /opt/audioapp/backend/myproject/settings.py audioapp_backend:/app/myproject/settings.py
docker compose -f docker-compose.production.yml restart backend
```

**Permanent Fix:** Commit changes to git and rebuild image (on machine with more RAM)

---

### Issue 4: Server Crashes During Frontend Build

**Cause:** npm build needs 1-2GB RAM, server has 3.8GB total

**Solution:** Build on local machine or use CI/CD with more resources

---

## 📊 **Monitoring Commands**

### Check Container Status:
```bash
cd /opt/audioapp
docker compose -f docker-compose.production.yml ps
```

### Check Memory Usage:
```bash
free -h
docker stats --no-stream
```

### Check Backend Logs:
```bash
docker logs --tail 100 audioapp_backend
docker logs -f audioapp_backend  # Follow mode
```

### Check Nginx Logs:
```bash
# Main nginx (not in Docker)
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Check Disk Space:
```bash
df -h
docker system df  # Docker disk usage
```

### Test API Endpoints:
```bash
# Login test
curl -s https://audio.precisepouchtrack.com/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"audioadmin123"}'

# Health check
curl -s https://audio.precisepouchtrack.com/api/

# Projects list (requires auth token)
curl -s https://audio.precisepouchtrack.com/api/projects/ \
  -H "Authorization: Token YOUR_TOKEN_HERE"
```

---

## 🔄 **Updating the Application**

### Backend Updates:

```bash
cd /opt/audioapp

# Pull latest code
git pull origin main

# Copy updated files to container
sudo docker cp backend/myproject/settings.py audioapp_backend:/app/myproject/settings.py
sudo docker cp backend/accounts/views.py audioapp_backend:/app/accounts/views.py
# ... copy other changed files

# Restart services
docker compose -f docker-compose.production.yml restart backend

# If database changes:
docker exec audioapp_backend python manage.py migrate
```

### Frontend Updates:

```bash
# Build on local machine first!
# Then on server:

cd /opt/audioapp
docker compose -f docker-compose.production.yml restart frontend

# Or if you rebuilt the image elsewhere:
docker compose -f docker-compose.production.yml pull frontend
docker compose -f docker-compose.production.yml up -d frontend
```

---

## 🎯 **Client-Side Processing Setup**

### Current Status:
- ✅ `/AudioUpload` page has client-side processing toggle
- ❌ `/project/27` page does NOT have toggle (requires frontend rebuild)

### To Use Client-Side Processing:
1. Navigate to: https://audio.precisepouchtrack.com/AudioUpload
2. Look for toggle above file selector
3. Switch to "🖥️ Process on My Device"
4. Select and process file (uses your computer's CPU/GPU)

### Benefits:
- ✅ Much faster processing
- ✅ No server memory usage
- ✅ No upload time
- ✅ No 502 errors

---

## 📝 **Important File Locations**

### On Server:
- **App Root:** `/opt/audioapp/`
- **Backend Source:** `/opt/audioapp/backend/`
- **Frontend Source:** `/opt/audioapp/frontend/audio-waveform-visualizer/`
- **Docker Compose:** `/opt/audioapp/docker-compose.production.yml`
- **Nginx Config:** `/etc/nginx/sites-available/audio.precisepouchtrack.com`
- **SSL Certs:** `/etc/letsencrypt/live/audio.precisepouchtrack.com/`

### Inside Containers:
- **Backend:** `/app/` (in audioapp_backend container)
- **Frontend:** `/usr/share/nginx/html/` (in audioapp_frontend container)

---

## 🔑 **Critical Files That Need Fixes**

### 1. `/opt/audioapp/backend/myproject/settings.py`

**Required Change:**
```python
# Line ~48 - MUST read from environment
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# NOT hardcoded like this (WRONG):
# ALLOWED_HOSTS = ['192.168.148.110', 'localhost', '127.0.0.1']
```

### 2. `/opt/audioapp/backend/accounts/views.py`

**Required Changes:**
```python
@method_decorator(csrf_exempt, name='dispatch')
class CustomAuthToken(ObtainAuthToken):
    permission_classes = [permissions.AllowAny]  # ADD THIS
    
    def post(self, request, *args, **kwargs):
        # ... existing code ...
        
        # Use get_or_create instead of direct access:
        subscription, created = UserSubscription.objects.get_or_create(user=user)
        # NOT: subscription = user.subscription (can fail)
```

### 3. `/opt/audioapp/frontend/audio-waveform-visualizer/.env.production`

**Verify these values:**
```bash
REACT_APP_API_URL=https://audio.precisepouchtrack.com/api
REACT_APP_WS_URL=wss://audio.precisepouchtrack.com/ws
NODE_ENV=production
```

---

## 🚀 **Complete Restart Recovery Procedure**

### After Server Reboot or Container Restart:

```bash
# 1. Navigate to app directory
cd /opt/audioapp

# 2. Check all containers are up
docker compose -f docker-compose.production.yml ps

# 3. If containers are down, start them
docker compose -f docker-compose.production.yml up -d

# 4. Run the fix script
/opt/audioapp/fix-after-restart.sh

# 5. Check swap is active
swapon --show

# 6. Verify memory
free -h

# 7. Test the application
curl -s https://audio.precisepouchtrack.com/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"audioadmin123"}' | head -c 100

# 8. Open browser and hard refresh
# Windows/Linux: Ctrl + Shift + R
# Mac: Cmd + Shift + R
```

---

## 📈 **System Requirements & Recommendations**

### Current Server (Minimum):
- ✅ 3.8GB RAM
- ✅ 4 CPU cores
- ✅ 143GB disk
- ⚠️ No swap (need to add)

### Recommended for Production:
- 💰 8GB RAM (allows frontend builds)
- 💰 4+ CPU cores
- 💰 4GB swap
- 💰 200GB+ disk

### Cost Optimization:
If staying with 3.8GB server:
- ✅ Stop Celery worker (saves 432MB)
- ✅ Add 4GB swap (prevents crashes)
- ✅ Build frontend elsewhere (local machine or CI/CD)
- ✅ Use client-side processing for uploads

---

## 🔗 **Useful Links**

- **Live Site:** https://audio.precisepouchtrack.com
- **Admin Panel:** https://audio.precisepouchtrack.com/admin/
- **Standalone Upload:** https://audio.precisepouchtrack.com/AudioUpload
- **API Root:** https://audio.precisepouchtrack.com/api/

---

## 📞 **Emergency Contacts**

### If Site is Down:

1. **Check containers:**
   ```bash
   docker compose -f /opt/audioapp/docker-compose.production.yml ps
   ```

2. **Check logs:**
   ```bash
   docker logs audioapp_backend --tail 50
   ```

3. **Restart everything:**
   ```bash
   cd /opt/audioapp
   docker compose -f docker-compose.production.yml restart
   /opt/audioapp/fix-after-restart.sh
   ```

4. **Nuclear option (full restart):**
   ```bash
   cd /opt/audioapp
   docker compose -f docker-compose.production.yml down
   docker compose -f docker-compose.production.yml up -d
   /opt/audioapp/fix-after-restart.sh
   ```

---

## ✅ **Success Checklist**

After applying fixes, verify:

- [ ] Login works: https://audio.precisepouchtrack.com/login
- [ ] API responds: `curl https://audio.precisepouchtrack.com/api/`
- [ ] Projects load: https://audio.precisepouchtrack.com/projects
- [ ] File upload works (or shows proper error)
- [ ] Memory available: `free -h` shows >500MB available
- [ ] Swap active: `swapon --show` shows swap
- [ ] Logs clean: `docker logs audioapp_backend --tail 10` no errors

---

**Last Updated:** February 28, 2026  
**Maintained By:** Nick D.  
**Server IP:** 82.165.221.205
