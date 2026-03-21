#!/bin/bash
#
# Frontend Deployment Script
# Copies the latest build files into the running Docker container
# WITHOUT requiring a full container rebuild
#
# Usage: ./deploy-frontend.sh
#

set -e  # Exit on any error

echo "🚀 Deploying Frontend to Docker Container..."
echo

# Check if container is running
if ! docker ps | grep -q audioapp_frontend; then
    echo "❌ Error: audioapp_frontend container is not running"
    echo "   Start it with: docker start audioapp_frontend"
    exit 1
fi

# Check if build directory exists
if [ ! -d "/opt/audioapp/frontend/build" ]; then
    echo "❌ Error: Build directory not found at /opt/audioapp/frontend/build"
    echo "   Build the frontend first on your local machine and upload via scp"
    exit 1
fi

# Display build info
echo "📦 Build files location: /opt/audioapp/frontend/build"
BUILD_DATE=$(stat -c %y /opt/audioapp/frontend/build/index.html 2>/dev/null | cut -d' ' -f1 || echo "Unknown")
echo "📅 Build date: $BUILD_DATE"
echo

# Get current main JS file being served
CURRENT_JS=$(docker exec audioapp_frontend cat /usr/share/nginx/html/index.html 2>/dev/null | grep -o 'main\.[^"]*\.js' | head -1 || echo "unknown")
echo "📄 Current JS file: $CURRENT_JS"

# Get new main JS file from build
NEW_JS=$(cat /opt/audioapp/frontend/build/index.html | grep -o 'main\.[^"]*\.js' | head -1 || echo "unknown")
echo "📄 New JS file: $NEW_JS"
echo

# Confirm deployment
if [ "$CURRENT_JS" = "$NEW_JS" ]; then
    echo "⚠️  Warning: New build appears to be the same as current version"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Deployment cancelled"
        exit 0
    fi
fi

# Copy build files to container (Docker port 3001)
echo "📋 Copying build files to Docker container..."
docker cp /opt/audioapp/frontend/build/. audioapp_frontend:/usr/share/nginx/html/

if [ $? -eq 0 ]; then
    echo "✅ Files copied to container"
else
    echo "❌ Failed to copy files to container"
    exit 1
fi

# Copy build files to nginx root (public domain)
echo "📋 Copying build files to nginx root (public domain)..."
rsync -a --delete /opt/audioapp/frontend/build/ /opt/audioapp/frontend/audio-waveform-visualizer/build/

if [ $? -eq 0 ]; then
    echo "✅ Files copied to nginx root"
else
    echo "❌ Failed to copy files to nginx root"
    exit 1
fi

# Fix permissions for nginx
echo "🔐 Setting correct permissions for nginx..."
chmod -R 755 /opt/audioapp/frontend/audio-waveform-visualizer/build

# Fix permissions
echo "🔒 Setting correct permissions..."
docker exec audioapp_frontend chmod -R 755 /usr/share/nginx/html/static

# Reload nginx
echo "🔄 Reloading nginx..."
docker exec audioapp_frontend nginx -s reload

if [ $? -eq 0 ]; then
    echo "✅ Nginx reloaded successfully"
else
    echo "⚠️  Warning: Nginx reload may have failed"
fi

echo
echo "✨ Frontend Deployment Complete!"
echo
echo "🌐 Application accessible at:"
echo "   - Local: http://localhost:3001"
echo "   - Public: http://82.165.221.205:3001"
echo
echo "📊 To verify deployment:"
echo "   curl -s http://localhost:3001/ | grep -o 'main\.[^\"]*\.js'"
echo
echo "⚠️  IMPORTANT: Browser Cache Issue"
echo "   Your browser may have cached the old version."
echo "   To see the new version:"
echo
echo "   🔄 Hard Refresh (recommended):"
echo "      - Windows/Linux: Ctrl + Shift + R  or  Ctrl + F5"
echo "      - Mac: Cmd + Shift + R"
echo
echo "   🧹 Or clear browser cache:"
echo "      - Chrome: Settings → Privacy → Clear browsing data"
echo "      - Firefox: Settings → Privacy → Clear Data"
echo
echo "   🕵️  Or use Incognito/Private mode (Ctrl + Shift + N)"
echo
echo "💡 Note: Changes will persist until container restart"
echo "   To make permanent, rebuild the Docker image or add volume mount"
echo
