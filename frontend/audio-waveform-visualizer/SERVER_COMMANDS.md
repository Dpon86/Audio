# Server Commands - Deploy Frontend

## Quick Reference

After transferring the build folder to the server, run these commands on the server:

```bash
# Navigate to frontend directory
cd /root/frontend/audio-waveform-visualizer

# Rebuild Docker container (fast - just copies files)
docker compose -f docker-compose.production.yml build frontend

# Restart container
docker compose -f docker-compose.production.yml up -d frontend

# Verify it's running
docker compose -f docker-compose.production.yml ps

# Check logs if needed
docker compose -f docker-compose.production.yml logs frontend
```

## What Changed

This deployment fixes the **localhost API URL bug**:

### Problem
- Frontend was calling `http://localhost:8000` instead of production server
- All API requests failed (file uploads, transcription, etc.)
- Browser console showed: `Failed to fetch http://localhost:8000/api/...`

### Solution Applied
1. ✅ Fixed `.env` file - changed to production URL
2. ✅ Exported `API_BASE_URL` from `src/config/api.js`
3. ✅ Replaced all hardcoded `http://localhost:8000` URLs with `${API_BASE_URL}` template literals
4. ✅ Added import statements to all files using the variable
5. ✅ Fixed template literal syntax (backticks)
6. ✅ Corrected import paths in ProjectTabs components
7. ✅ Clean rebuild - new bundle hash: `main.290572cc.js` (1.33 MB)

### Files Modified
- `src/config/api.js` - Exported API_BASE_URL
- `src/contexts/ProjectTabContext.js` - Import + use API_BASE_URL
- `src/components/DebugPanel.js` - Import + use API_BASE_URL  
- `src/components/PDFRegionSelector.js` - Import + use API_BASE_URL
- `src/components/Tab3Review.js` - Import + use API_BASE_URL
- `src/components/Tab4Review.js` - Import + use API_BASE_URL
- `src/components/Pricing/PricingPage.js` - Import + use API_BASE_URL
- `src/screens/ProjectDetailPage.js` - Import + use API_BASE_URL
- All `src/components/ProjectTabs/*.js` files - Import + use API_BASE_URL

### Environment Variables
```
REACT_APP_API_URL=https://audio.precisepouchtrack.com
REACT_APP_WS_URL=wss://audio.precisepouchtrack.com/ws
```

## Verification Steps

After deploying, test in browser:

1. **Open DevTools** (F12) → Network tab
2. **Visit**: https://audio.precisepouchtrack.com
3. **Upload a file** or navigate around
4. **Check API calls** - should see:
   - ✅ `https://audio.precisepouchtrack.com/api/projects/`
   - ✅ `https://audio.precisepouchtrack.com/api/infrastructure/status/`
   - ❌ NOT `http://localhost:8000/...`

5. **Check Console** - should be no errors about localhost

## Expected Results

- File uploads work
- Transcription works  
- PDF comparison works
- All tabs functional
- No CORS errors
- No localhost connection errors

## Rollback (if needed)

If something goes wrong:

```bash
# Stop the container
docker compose -f docker-compose.production.yml down frontend

# Restore previous build from backup (if you made one)
# Or rebuild from previous version

# Restart
docker compose -f docker-compose.production.yml up -d frontend
```

## Build Information

- **Build Date**: March 5, 2026
- **Build Size**: 1.33 MB (main JS bundle)
- **Bundle Hash**: `main.290572cc.js`
- **Previous Hash**: `main.84b4c137.js` (broken version)
- **Compiler**: react-app-rewired
- **Warnings**: Only ESLint warnings (unused variables, missing deps) - non-breaking
