# Build Frontend Locally & Deploy to Server

**Quick Guide:** Build the React app on your Windows machine, then transfer to Linux server (avoids memory issues and is much faster).

---

## Step 1: Build Frontend Locally (Windows)

### 1.1 Navigate to Frontend Directory

```powershell
cd C:\Users\NickD\Documents\Github\Audio\frontend\audio-waveform-visualizer
```

### 1.2 Install Dependencies (if not already done)

```powershell
npm install
```

### 1.3 Create Production Environment File

Check if `.env.production` exists:

```powershell
Get-Content .env.production
```

**Should contain:**
```env
REACT_APP_API_URL=https://audio.precisepouchtrack.com/api
REACT_APP_WS_URL=wss://audio.precisepouchtrack.com/ws
NODE_ENV=production
GENERATE_SOURCEMAP=false
OPTIMIZE_CSS=false
```

**If it needs updating, edit it:**
```powershell
notepad .env.production
```

Replace `audio.precisepouchtrack.com` with your actual domain.

### 1.4 Build the Application

```powershell
npm run build
```

**This will:**
- Use `react-app-rewired` with your custom `config-overrides.js`
- Apply CSS optimization settings
- Create an optimized production build
- Take 2-5 minutes on your local machine

**When complete, you'll see:**
```
Creating an optimized production build...
Compiled successfully.

File sizes after gzip:

  XX KB  build/static/js/main.xxxxxxxx.js
  XX KB  build/static/css/main.xxxxxxxx.css

The project was built successfully!
```

### 1.5 Verify Build Output

```powershell
# Check that build folder was created
dir build

# Should see:
# - index.html
# - asset-manifest.json
# - static/ (folder with js, css, media)
# - favicon.ico, logo192.png, etc.

# Check size
Get-ChildItem build -Recurse | Measure-Object -Property Length -Sum
```

---

## Step 2: Transfer to Server

### Option A: Using SCP (Recommended)

**2.1 Open PowerShell and navigate to the build directory:**

```powershell
cd C:\Users\NickD\Documents\Github\Audio\frontend\audio-waveform-visualizer
```

**2.2 Transfer the entire build folder:**

```powershell
# Create the build directory on server first
ssh nickd@82.165.221.205 "mkdir -p /opt/audioapp/frontend/audio-waveform-visualizer/build"

# Transfer all build files
scp -r build/* nickd@82.165.221.205:/opt/audioapp/frontend/audio-waveform-visualizer/build/
```

**Enter your server password when prompted.**

**Expected Output:**
```
index.html                     100%   3KB   500KB/s   00:00
asset-manifest.json            100%   1KB   400KB/s   00:00
favicon.ico                    100%  15KB   1.2MB/s   00:00
...
main.abc123.js                 100% 250KB   5.0MB/s   00:00
main.abc123.css                100%  50KB   2.5MB/s   00:00
```

### Option B: Using WinSCP (GUI Alternative)

If you prefer a graphical interface:

1. **Download WinSCP:** https://winscp.net/
2. **Connect to your server:**
   - Host: `82.165.221.205`
   - User: `nickd`
   - Password: Your server password
3. **Navigate to:** `/opt/audioapp/frontend/audio-waveform-visualizer/`
4. **Create `build` folder** (if it doesn't exist)
5. **Drag and drop** all files from `C:\Users\NickD\Documents\Github\Audio\frontend\audio-waveform-visualizer\build\` to the server's `build` folder

---

## Step 3: Update Docker Configuration (Server-Side)

Now we need to modify the Docker setup to use your pre-built files instead of building in the container.

**3.1 SSH into your server:**

```powershell
ssh nickd@82.165.221.205
```

**3.2 Create a simplified Dockerfile for pre-built frontend:**

```bash
cd /opt/audioapp/frontend/audio-waveform-visualizer
nano Dockerfile.prebuilt
```

**Add this content:**

```dockerfile
FROM nginx:alpine

# Copy pre-built files from local build directory
COPY build/ /usr/share/nginx/html/

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

**Save:** Ctrl+O, Enter, Ctrl+X

**3.3 Update docker-compose.production.yml:**

```bash
cd /opt/audioapp
nano docker-compose.production.yml
```

**Find the frontend service section and change:**

```yaml
  # React Frontend
  frontend:
    build:
      context: ./frontend/audio-waveform-visualizer
      dockerfile: Dockerfile.prebuilt  # Changed from Dockerfile.production
    container_name: audioapp_frontend
    restart: unless-stopped
    networks:
      - audioapp_network
    ports:
      - "3000:80"
```

**Save:** Ctrl+O, Enter, Ctrl+X

---

## Step 4: Rebuild & Restart Frontend Container

**4.1 Stop the current frontend container:**

```bash
docker compose -f docker-compose.production.yml stop frontend
```

**4.2 Rebuild frontend container (now uses pre-built files):**

```bash
docker compose -f docker-compose.production.yml build frontend
```

**This should only take 10-20 seconds** since it's just copying files, not running npm build!

**4.3 Start the frontend container:**

```bash
docker compose -f docker-compose.production.yml up -d frontend
```

**4.4 Verify it's running:**

```bash
docker ps | grep frontend

# Check logs
docker logs audioapp_frontend

# Should see:
# /docker-entrypoint.sh: Configuration complete; ready for start up
```

---

## Step 5: Test Your Deployment

**5.1 Test directly (from server):**

```bash
curl http://localhost:3000
# Should return HTML content with your React app
```

**5.2 Test through Nginx (from your browser):**

Visit: `https://audio.precisepouchtrack.com`

**5.3 Verify all features work:**

- [ ] Tab 1 (Upload) - File upload works
- [ ] Tab 2 (Transcribe) - Transcription starts
- [ ] Tab 3 (Duplicates) - Algorithm selector appears
- [ ] Settings card shows before clicking Start
- [ ] PDF region selector works (if using PDF-Guided algorithm)
- [ ] Tab 4 (Results) - Waveform loads
- [ ] Silence alignment controls appear (threshold, search range, min duration)
- [ ] Tab 5 (Compare PDF) - Side-by-side comparison respects selected ranges

**5.4 Check browser console (F12):**

- No JavaScript errors
- API calls go to correct URL (`https://audio.precisepouchtrack.com/api`)

---

## Future Updates Workflow

Every time you update the frontend code:

### On Your Windows Machine:

```powershell
cd C:\Users\NickD\Documents\Github\Audio\frontend\audio-waveform-visualizer

# Make your code changes...

# Rebuild
npm run build

# Transfer to server
scp -r build/* nickd@82.165.221.205:/opt/audioapp/frontend/audio-waveform-visualizer/build/
```

### On Your Server:

```bash
cd /opt/audioapp

# Rebuild and restart frontend container
docker compose -f docker-compose.production.yml build frontend
docker compose -f docker-compose.production.yml up -d frontend

# Check logs
docker logs -f audioapp_frontend
```

**That's it!** No need to rebuild on the server every time.

---

## Troubleshooting

### Build Fails Locally

```powershell
# Clear node_modules and reinstall
cd C:\Users\NickD\Documents\Github\Audio\frontend\audio-waveform-visualizer
Remove-Item -Recurse -Force node_modules
Remove-Item -Force package-lock.json
npm install
npm run build
```

### SCP Transfer Fails

```powershell
# Test SSH connection first
ssh nickd@82.165.221.205 "echo Connection successful"

# If SSH works but SCP doesn't, try with full path:
scp -r C:\Users\NickD\Documents\Github\Audio\frontend\audio-waveform-visualizer\build\* nickd@82.165.221.205:/opt/audioapp/frontend/audio-waveform-visualizer/build/

# Or use verbose mode to see what's happening:
scp -v -r build/* nickd@82.165.221.205:/opt/audioapp/frontend/audio-waveform-visualizer/build/
```

### Files Not Updating in Browser

```bash
# On server, verify files were actually copied
ssh nickd@82.165.221.205
ls -la /opt/audioapp/frontend/audio-waveform-visualizer/build/
ls -la /opt/audioapp/frontend/audio-waveform-visualizer/build/static/js/

# Check file timestamps - should be recent
```

**In browser:**
- Hard refresh: `Ctrl + Shift + R` or `Ctrl + F5`
- Clear cache in DevTools (F12 → Network tab → check "Disable cache")

### Container Won't Start

```bash
# Check logs for errors
docker logs audioapp_frontend

# Common issues:
# 1. build/ directory is empty
ls -la /opt/audioapp/frontend/audio-waveform-visualizer/build/

# 2. nginx.conf is missing or invalid
docker exec audioapp_frontend nginx -t

# Rebuild from scratch
docker compose -f docker-compose.production.yml stop frontend
docker compose -f docker-compose.production.yml rm -f frontend
docker compose -f docker-compose.production.yml build --no-cache frontend
docker compose -f docker-compose.production.yml up -d frontend
```

---

## Quick Reference Commands

### Build & Deploy (Full Process)

**On Windows:**
```powershell
cd C:\Users\NickD\Documents\Github\Audio\frontend\audio-waveform-visualizer
npm run build
scp -r build/* nickd@82.165.221.205:/opt/audioapp/frontend/audio-waveform-visualizer/build/
```

**On Server:**
```bash
cd /opt/audioapp
docker compose -f docker-compose.production.yml build frontend
docker compose -f docker-compose.production.yml up -d frontend
docker logs -f audioapp_frontend
```

### One-Line Update (after initial setup)

**From Windows:**
```powershell
cd C:\Users\NickD\Documents\Github\Audio\frontend\audio-waveform-visualizer ; npm run build ; scp -r build/* nickd@82.165.221.205:/opt/audioapp/frontend/audio-waveform-visualizer/build/ ; ssh nickd@82.165.221.205 "cd /opt/audioapp && docker compose -f docker-compose.production.yml build frontend && docker compose -f docker-compose.production.yml up -d frontend"
```

---

## Advantages of This Approach

✅ **Fast:** Build takes 2-5 minutes locally vs 30+ minutes on server  
✅ **No Memory Issues:** Your Windows machine has plenty of RAM  
✅ **No Swap Needed:** Server stays clean and efficient  
✅ **Easier Debugging:** See build errors immediately on your dev machine  
✅ **Reproducible:** Same build environment every time  
✅ **Version Control:** Keep track of what's deployed  

---

## Next Steps

After successfully deploying:

1. **Set up a deployment script** (optional):
   - Create `deploy-frontend.ps1` to automate the build + transfer + restart process
   
2. **Add to Git workflow:**
   - Tag releases after successful deployments
   - Document which build is currently live

3. **Monitor performance:**
   - Check browser load times
   - Monitor server resource usage
   - Review Nginx access logs

---

**Questions?** Check the main [LINUX_DEPLOYMENT_GUIDE.md](./LINUX_DEPLOYMENT_GUIDE.md) for full server setup details.
