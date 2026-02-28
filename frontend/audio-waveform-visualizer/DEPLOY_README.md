# Frontend Deployment - Quick Start

Choose your deployment method:

## Method 1: Automated Deployment Script (Easiest!)

Run the PowerShell deployment script that handles everything:

```powershell
# From this directory (frontend/audio-waveform-visualizer)
.\deploy.ps1
```

This will:
1. Build the React app locally (2-5 minutes)
2. Transfer files to your server via SCP
3. Rebuild the Docker container
4. Restart the frontend service
5. Verify everything is running

**First Time Setup:**
- Make sure `.env.production` has your correct domain
- Ensure you can SSH to your server: `ssh nickd@82.165.221.205`

---

## Method 2: Manual Step-by-Step

### Step 1: Build locally
```powershell
npm run build
```

### Step 2: Transfer to server
```powershell
scp -r build/* nickd@82.165.221.205:/opt/audioapp/frontend/audio-waveform-visualizer/build/
```

### Step 3: Restart on server
```powershell
ssh nickd@82.165.221.205
cd /opt/audioapp
docker compose -f docker-compose.production.yml build frontend
docker compose -f docker-compose.production.yml up -d frontend
```

---

## Files in This Directory

- **deploy.ps1** - Automated deployment script
- **Dockerfile.prebuilt** - Docker config for pre-built files (fast, recommended)
- **Dockerfile.production** - Docker config for building on server (slower)
- **nginx.conf** - Nginx configuration for serving the React app
- **.env.production** - Production environment variables (API URL, etc.)
- **config-overrides.js** - Custom webpack config for CSS optimization

---

## Troubleshooting

### Build fails locally?
```powershell
# Clear and reinstall
Remove-Item -Recurse -Force node_modules
npm install
npm run build
```

### SCP transfer fails?
```powershell
# Test SSH first
ssh nickd@82.165.221.205 "echo 'Connection works!'"

# Try with verbose output
scp -v -r build/* nickd@82.165.221.205:/opt/audioapp/frontend/audio-waveform-visualizer/build/
```

### Changes not showing in browser?
- Hard refresh: `Ctrl + Shift + R`
- Clear browser cache
- Check the container rebuilt: `docker logs audioapp_frontend`

---

## Full Documentation

For complete deployment guide including server setup, see:
- **[BUILD_AND_DEPLOY_FRONTEND.md](../../docs/BUILD_AND_DEPLOY_FRONTEND.md)** - Detailed frontend deployment guide
- **[LINUX_DEPLOYMENT_GUIDE.md](../../docs/LINUX_DEPLOYMENT_GUIDE.md)** - Complete server setup guide

---

## Quick Reference

**Current production URL:** https://audio.precisepouchtrack.com

**Server details:**
- User: nickd
- IP: 82.165.221.205
- Path: /opt/audioapp/frontend/audio-waveform-visualizer/

**Update workflow:**
1. Make changes to React code
2. Run `.\deploy.ps1`
3. Test at https://audio.precisepouchtrack.com
