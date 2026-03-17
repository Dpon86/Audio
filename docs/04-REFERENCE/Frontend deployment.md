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

### What the Script Does

1. ✅ Checks if container is running
2. ✅ Verifies build directory exists
3. ✅ Shows current vs new version
4. ✅ Copies build files into container
5. ✅ Fixes file permissions
6. ✅ Reloads nginx
7. ✅ Displays access URLs

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
- **Build files**: `/opt/audioapp/frontend/build/`
- **Container files**: `/usr/share/nginx/html/` (inside container)
- **Docker Compose**: `/opt/audioapp/docker-compose.production.yml`

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
