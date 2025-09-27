#!/bin/bash
# Audio Repetitive Detection - Development Startup Script

echo "========================================"
echo " Audio Repetitive Detection Dev Setup"
echo "========================================"

read -p "Start React frontend too? (y/N): " START_FRONTEND
START_FRONTEND=${START_FRONTEND,,}  # Convert to lowercase

echo ""
echo "🔧 Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not running"
    echo "Please install Docker Desktop and make sure it's running"
    exit 1
fi

echo "✅ Docker is available"

echo ""
echo "🚀 Starting Redis container..."
osascript -e 'tell app "Terminal" to do script "docker run --rm -p 6379:6379 redis"' &

echo "⏳ Waiting for Redis to start..."
sleep 5

echo ""
echo "🚀 Starting Celery worker..."
osascript -e 'tell app "Terminal" to do script "cd '$(pwd)' && celery -A myproject worker --loglevel=info"' &

echo "⏳ Waiting for Celery to start..."
sleep 3

if [[ "$START_FRONTEND" == "y" ]]; then
    echo ""
    echo "🚀 Starting React frontend..."
    osascript -e 'tell app "Terminal" to do script "cd '$(pwd)'/../frontend/audio-waveform-visualizer && npm start"' &
    echo "⏳ Waiting for frontend to start..."
    sleep 3
fi

echo ""
echo "🚀 Starting Django development server..."
echo ""
echo "✅ All services should be starting!"
echo "🌐 Django will be available at: http://127.0.0.1:8000"
echo "📊 Redis is running on: localhost:6379"
echo "⚡ Celery worker is running"
if [[ "$START_FRONTEND" == "y" ]]; then
    echo "⚛️  React frontend will be available at: http://localhost:3000"
fi
echo ""
echo "Press Ctrl+C to stop the Django server"
if [[ "$START_FRONTEND" == "y" ]]; then
    echo "Close the React, Redis and Celery terminal windows to stop those services"
else
    echo "Close the Redis and Celery terminal windows to stop those services"
    echo "To start frontend separately: cd ../frontend/audio-waveform-visualizer && npm start"
fi
echo ""

python manage.py runserver

echo ""
echo "🛑 Django server stopped"
echo "Don't forget to close Redis and Celery terminal windows if needed"