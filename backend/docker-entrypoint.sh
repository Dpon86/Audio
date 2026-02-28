#!/bin/bash
set -e

echo "=== Audio App Backend Starting ==="

# Wait for database
echo "Waiting for PostgreSQL..."
until pg_isready -h $DATABASE_HOST -p $DATABASE_PORT -U $DATABASE_USER 2>/dev/null; do
  echo "PostgreSQL not ready, waiting..."
  sleep 2
done
echo "✓ PostgreSQL is ready!"

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput
echo "✓ Migrations complete!"

# Create static directory if it doesn't exist
mkdir -p /app/staticfiles /app/media
echo "✓ Static directories created!"

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput
echo "✓ Static files collected!"

# Create superuser if needed
echo "Checking for admin user..."
python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@precisepouchtrack.com', 'audioadmin123')
    print('✓ Superuser created: admin / audioadmin123 (CHANGE THIS!)')
else:
    print('✓ Superuser already exists')
END

echo "=== Backend Ready - Starting Gunicorn ==="

# Execute the main command (Gunicorn)
exec "$@"
