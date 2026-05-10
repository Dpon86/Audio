#!/bin/bash
set -e

echo "=== Step 1: git pull ==="
cd /opt/audioapp
git pull origin master

echo "=== Step 2: find backend container ==="
BACKEND_CONTAINER=$(docker ps --format "{{.Names}}" | grep -E "audioapp_backend|_audioapp_backend" | grep -v celery | head -1)
echo "Container: $BACKEND_CONTAINER"

if [ -z "$BACKEND_CONTAINER" ]; then
  echo "ERROR: Could not find backend container"
  docker ps --format "{{.Names}}"
  exit 1
fi

echo "=== Step 3: copy updated views file into container ==="
docker cp /opt/audioapp/backend/audioDiagnostic/views/ai_detection_views.py \
  $BACKEND_CONTAINER:/app/audioDiagnostic/views/ai_detection_views.py

echo "=== Step 4: restart backend container ==="
docker restart $BACKEND_CONTAINER

echo "=== Done ==="
