#!/bin/bash
# EMERGENCY CELERY FIX - Run this on the server immediately
# Task stuck in PENDING means workers are down or broken

echo "=== STEP 1: Check Celery Container Status ==="
docker ps --filter name=audioapp_celery --format 'table {{.Names}}\t{{.Status}}\t{{.State}}'

echo -e "\n=== STEP 2: Check Last 50 Lines of Celery Logs ==="
docker logs --tail 50 audioapp_celery

echo -e "\n=== STEP 3: Check for UnboundLocalError (the bug we fixed but never deployed) ==="
docker logs audioapp_celery 2>&1 | grep -A 5 "UnboundLocalError\|cannot access local variable"

echo -e "\n=== STEP 4: Check Current Git Status ==="
cd /opt/audioapp
git log --oneline -5
echo "Current commit:"
git rev-parse --short HEAD

echo -e "\n=== STEP 5: Pull Latest Code (includes UnboundLocalError fix) ==="
git pull

echo -e "\n=== STEP 6: RESTART CELERY (loads new code into memory) ==="
docker restart audioapp_celery

echo -e "\nWaiting 5 seconds for Celery to start..."
sleep 5

echo -e "\n=== STEP 7: Verify Celery Restarted Successfully ==="
docker logs --tail 30 audioapp_celery | grep -E "ready|celery@|mingle"

echo -e "\n=== STEP 8: Check Active Workers ==="
docker exec audioapp_celery celery -A myproject inspect active

echo -e "\n=== DONE ==="
echo "If you see 'celery@hostname ready' above, workers are running."
echo "Try server-side assembly again. It should work now."
