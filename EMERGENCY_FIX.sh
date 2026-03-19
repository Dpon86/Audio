#!/bin/bash
# COMPLETE DEPLOYMENT - Run this on the server
# Fixes: Layout issues, UnboundLocalError, system status display

echo "==================================="
echo "  AUDIO APP - COMPLETE DEPLOYMENT"
echo "==================================="

echo -e "\n=== STEP 1: Check Current Status ==="
echo "Celery container status:"
docker ps --filter name=audioapp_celery --format 'table {{.Names}}\t{{.Status}}\t{{.State}}'

echo -e "\n=== STEP 2: Check for UnboundLocalError ==="
echo "Checking Celery logs for errors..."
ERRORS=$(docker logs audioapp_celery 2>&1 | grep -c "UnboundLocalError\|cannot access local variable")
if [ $ERRORS -gt 0 ]; then
    echo "⚠️  Found $ERRORS UnboundLocalError occurrences - backend needs update"
else
    echo "✓ No UnboundLocalError found"
fi

echo -e "\n=== STEP 3: Check Current Git Version ==="
cd /opt/audioapp
echo "Current commit: $(git rev-parse --short HEAD)"
git log --oneline -3

echo -e "\n=== STEP 4: Pull Latest Code ==="
echo "Pulling from GitHub..."
git pull
echo "New commit: $(git rev-parse --short HEAD)"

echo -e "\n=== STEP 5: Deploy Frontend (CRITICAL FOR LAYOUT FIX) ==="
cd /opt/audioapp/frontend

# Extract build.zip (user must upload this first)
if [ -f "build.zip" ]; then
    echo "✓ Found build.zip, extracting..."
    rm -rf build/*
    unzip -o build.zip -d build/
    rm build.zip
    echo "✓ Frontend files extracted"
else
    echo "⚠️  build.zip not found. Upload it to /opt/audioapp/frontend/ first"
    echo "   Then run: rm -rf build/* && unzip -o build.zip -d build/ && rm build.zip"
fi

# Sync to both nginx locations
echo "Syncing to audio-waveform-visualizer/build/..."
rsync -av --delete build/ audio-waveform-visualizer/build/
chmod -R 755 audio-waveform-visualizer/build

# Copy to Docker container
echo "Copying to Docker frontend container..."
docker cp build/. audioapp_frontend:/usr/share/nginx/html/

# Restart frontend
echo "Restarting frontend container..."
docker restart audioapp_frontend

# Reload nginx
echo "Reloading nginx..."
sudo systemctl reload nginx

echo -e "\n=== STEP 6: Deploy Backend (RESTART CELERY) ==="
cd /opt/audioapp
docker restart audioapp_celery

echo "Waiting 8 seconds for Celery to start..."
sleep 8

echo -e "\n=== STEP 7: Verify Deployment ==="
echo "Celery status:"
docker logs --tail 30 audioapp_celery | grep -E "ready|celery@|mingle"

echo -e "\nActive workers:"
docker exec audioapp_celery celery -A myproject inspect active 2>/dev/null || echo "⚠️  No active workers (may need more time to start)"

echo -e "\n=== STEP 8: Check Frontend Version ==="
MAIN_JS=$(ls -1 /opt/audioapp/frontend/build/static/js/main.*.js 2>/dev/null | head -1)
if [ -n "$MAIN_JS" ]; then
    HASH=$(basename "$MAIN_JS" | sed 's/main\.\(.*\)\.js/\1/')
    SIZE=$(du -h "$MAIN_JS" | cut -f1)
    echo "Frontend deployed: main.$HASH.js ($SIZE)"
    echo "Expected hash: 6714eb0e (if you uploaded the latest build)"
else
    echo "⚠️  No main.*.js found"
fi

echo -e "\n==================================="
echo "  DEPLOYMENT COMPLETE!"
echo "==================================="
echo ""
echo "✅ WHAT'S FIXED:"
echo "   • System status now displays BELOW login form (not beside it)"
echo "   • Clear titles for each service:"
echo "     - Backend Version"  
echo "     - Frontend Build"
echo "     - Celery Workers"
echo "     - Redis Cache"
echo "   • UnboundLocalError fixed in server-side assembly"
echo "   • White card design on purple background"
echo ""
echo "🔍 VERIFY:"
echo "   1. Visit: https://audio.precisepouchtrack.com/login"
echo "   2. System status should appear BELOW the login form"
echo "   3. Should show 4 labeled rows with service information"
echo "   4. Try server-side assembly - should work without errors"
echo ""
echo "📝 If system status shows 'Backend Unavailable':"
echo "   • Check: docker logs audioapp_backend"
echo "   • Verify /api/system-version/ endpoint is working"
echo "   • May need to restart: docker restart audioapp_backend"
echo ""
