# Frontend Deployment Guide

## Quick Deploy Script

Use the `deploy-frontend.sh` script to quickly deploy new frontend builds without rebuilding the Docker image.

### Usage

```bash
cd /opt/audioapp
./deploy-frontend.sh
```

### Workflow

1. **On your local Windows machine:**
   - Make code changes
   - Build the frontend:
     ```powershell
     cd C:\Users\NickD\Documents\Github\Audio\frontend\audio-waveform-visualizer
     npm run build
     ```
   - Upload to server:
     ```powershell
     scp -r build\* nickd@82.165.221.205:/opt/audioapp/frontend/build/
     ```

2. **On the server:**
   - Run the deployment script:
     ```bash
     cd /opt/audioapp
     ./deploy-frontend.sh
     ```

3. **Done!** The new frontend is live at:
   - http://localhost:3001 (local)
   - http://82.165.221.205:3001 (public)

4. **Clear Browser Cache** (IMPORTANT!)
   - Your browser may have cached the old version
   - **Hard Refresh**: 
     - Windows/Linux: `Ctrl + Shift + R` or `Ctrl + F5`
     - Mac: `Cmd + Shift + R`
   - Or use Incognito/Private mode (`Ctrl + Shift + N`)
   - Or clear browser cache completely

### What the Script Does

1. ✅ Checks if container is running
2. ✅ Verifies build directory exists
3. ✅ Shows current vs new version
4. ✅ Copies build files into Docker container (port 3001)
5. ✅ Copies build files to nginx root (public domain)
6. ✅ Fixes file permissions
7. ✅ Reloads nginx
8. ✅ Displays access URLs

### Important: Dual Deployment

The script deploys to **TWO locations**:

1. **Docker Container** (port 3001)
   - Location: Inside `audioapp_frontend` container at `/usr/share/nginx/html/`
   - Access: http://localhost:3001, http://82.165.221.205:3001
   - Used for: Direct container access

2. **Main Nginx** (public domain)
   - Location: `/opt/audioapp/frontend/audio-waveform-visualizer/build/`
   - Access: https://audio.precisepouchtrack.com
   - Used for: Production with SSL/HTTPS

Both locations get the same files to ensure consistency.

### Important Notes

⚠️ **Changes are temporary** - They persist until container restart

To make changes permanent, choose one:

**Option A: Add to docker-compose.yml (BEST)**
```yaml
frontend:
  volumes:
    - ./frontend/build:/usr/share/nginx/html:ro
```
Then: `docker-compose -f docker-compose.production.yml up -d frontend`

**Option B: Rebuild Docker Image**
```bash
cd /opt/audioapp
docker-compose -f docker-compose.production.yml build frontend
docker-compose -f docker-compose.production.yml up -d frontend
```

### Troubleshooting

**Browser still loading old version (main.37aff691.js instead of main.ccb12991.js):**

This is a browser cache issue. The server is serving the correct files, but your browser cached the old HTML/JS.

**Solution:**
1. **Hard Refresh** (clears cache for current page):
   - Windows/Linux: `Ctrl + Shift + R` or `Ctrl + F5`
   - Mac: `Cmd + Shift + R`
   
2. **Open DevTools and disable cache**:
   - Press `F12` to open DevTools
   - Go to Network tab
   - Check "Disable cache"
   - Refresh the page
   
3. **Clear browser cache completely**:
   - Chrome: `Settings → Privacy → Clear browsing data → Cached images and files`
   - Firefox: `Settings → Privacy → Clear Data → Cached Web Content`
   
4. **Use Incognito/Private mode**:
   - Chrome/Edge: `Ctrl + Shift + N`
   - Firefox: `Ctrl + Shift + P`

**Note:** As of the latest deployment, nginx is configured to prevent HTML caching, so hard refresh should always work.

**Container not running:**
```bash
docker start audioapp_frontend
```

**Check what's deployed:**
```bash
curl -s http://localhost:3001/ | grep -o 'main\.[^"]*\.js'
```

**View container logs:**
```bash
docker logs audioapp_frontend
```

**Manual deploy (if script fails):**
```bash
docker cp /opt/audioapp/frontend/build/. audioapp_frontend:/usr/share/nginx/html/
docker exec audioapp_frontend chmod -R 755 /usr/share/nginx/html/static
docker exec audioapp_frontend nginx -s reload
```

### File Locations

- **Script**: `/opt/audioapp/deploy-frontend.sh`
- **Build files upload destination**: `/opt/audioapp/frontend/build/`
- **Production nginx root**: `/opt/audioapp/frontend/audio-waveform-visualizer/build/`
- **Docker container files**: `/usr/share/nginx/html/` (inside container)
- **Docker Compose**: `/opt/audioapp/docker-compose.production.yml`
- **Main Nginx Config**: `/etc/nginx/sites-available/audioapp`
- **Container Nginx Config**: `/etc/nginx/conf.d/default.conf` (inside container)

### Nginx Cache Configuration

The nginx server is configured with smart caching:
- **HTML files** (`*.html`): NO CACHE - always fetches fresh version
- **JS/CSS/Images**: 1 year cache - cached until filename changes (content hash)

This means:
- ✅ When you deploy a new build, users get the new `index.html` immediately
- ✅ New `index.html` references new `main.HASH.js` filename
- ✅ Browser fetches the new JS file (different filename = not cached)
- ✅ Old JS files can be safely deleted from container

### Version Checking

The script automatically detects version changes by comparing the main JavaScript filename:
- Current: Shown in container's index.html
- New: Shown in build/index.html

Example:
```
📄 Current JS file: main.4773b4dc.js  (OLD)
📄 New JS file: main.ccb12991.js      (NEW)
```

### Automation

To auto-deploy after scp upload, add to your local script:

```powershell
# After scp upload
ssh nickd@82.165.221.205 "cd /opt/audioapp && ./deploy-frontend.sh"
```

Or create a one-liner:
```bash
scp -r build\* nickd@82.165.221.205:/opt/audioapp/frontend/build/ && ssh nickd@82.165.221.205 "cd /opt/audioapp && ./deploy-frontend.sh"
```

---

## Quick Reference: Browser Cache Clearing

### Why Browser Cache Causes Issues

When React builds your app, it generates files with content hashes:
- `main.37aff691.js` ← Old version
- `main.ccb12991.js` ← New version

If your browser cached the old `index.html`, it will keep loading `main.37aff691.js` even though the server has the new version.

### Solution Matrix

| Problem | Solution | How |
|---------|----------|-----|
| Browser loads old JS file | Hard Refresh | `Ctrl+Shift+R` or `Ctrl+F5` |
| Still showing old version | Open DevTools, disable cache | `F12` → Network → ☑ Disable cache |
| Need to test fresh | Incognito/Private mode | `Ctrl+Shift+N` |
| Multiple devices having issues | Clear all browser data | Settings → Privacy → Clear data |

### Verify Correct Version is Loading

1. Open browser DevTools (`F12`)
2. Go to **Network** tab
3. Refresh the page
4. Look for the main JS file being loaded
5. Should see: `main.ccb12991.js` ✅
6. If you see: `main.37aff691.js` ❌ - Do hard refresh!

### Check What Server is Serving

```bash
# On server
curl -s http://localhost:3001/ | grep -o 'main\.[^"]*\.js'

# Should output: main.ccb12991.js
```

If server shows correct version but browser doesn't → Browser cache issue!
