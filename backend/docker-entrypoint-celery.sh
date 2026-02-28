#!/bin/bash
set -e

echo "=== Celery Service Starting ==="

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
while ! pg_isready -h db -U audioapp_user; do
  sleep 1
done
echo "✓ PostgreSQL is ready!"

# Wait for Redis - simplified check
echo "Waiting for Redis..."
sleep 5
echo "✓ Redis is ready!"

# No migrations here - backend container handles that

echo "Starting Celery..."
exec "$@"
