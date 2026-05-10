#!/bin/bash
set -e

echo "=== Step 1: git pull ==="
cd /opt/audioapp
git pull origin master

echo "=== Step 2: rsync build files ==="
rsync -av --delete /opt/audioapp/frontend/build/ /opt/audioapp/frontend/audio-waveform-visualizer/build/

echo "=== Step 3: find frontend container ==="
FRONTEND_CONTAINER=$(docker ps --format "{{.Names}}" | grep -E "audioapp_frontend|_audioapp_frontend" | head -1)
echo "Container: $FRONTEND_CONTAINER"

if [ -n "$FRONTEND_CONTAINER" ]; then
    echo "=== Step 4: copy to nginx container ==="
    docker cp /opt/audioapp/frontend/build/. $FRONTEND_CONTAINER:/usr/share/nginx/html/
    echo "=== Step 5: restart container ==="
    docker restart $FRONTEND_CONTAINER
else
    echo "No frontend container found, skipping docker steps"
fi

echo "=== Step 6: reload nginx ==="
sudo systemctl reload nginx

echo "=== DEPLOY COMPLETE ==="
