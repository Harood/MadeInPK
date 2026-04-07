#!/bin/bash

# Exit on error
set -e

echo "ðŸš€ Starting MadeInPK Docker Entrypoint..."

# Wait for PostgreSQL to be ready
echo "â³ Waiting for PostgreSQL..."
while ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER"; do
  sleep 1
done
echo "âœ… PostgreSQL is ready!"

# Wait for Redis to be ready
echo "â³ Waiting for Redis..."
while ! redis-cli -h redis ping > /dev/null 2>&1; do
  sleep 1
done
echo "âœ… Redis is ready!"

# Run database migrations
echo "ðŸ”„ Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "ðŸ“¦ Collecting static files..."
python manage.py collectstatic --noinput --clear

# Create superuser if it doesn't exist (optional)
echo "ðŸ‘¤ Creating superuser (if needed)..."
python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('âœ… Superuser created: username=admin, password=admin123')
else:
    print('â„¹ï¸  Superuser already exists')
END

# Populate database with sample data (only for web service)
# Check if we're running the web service (not celery)
if [[ "$@" == *"daphne"* ]]; then
  if python manage.py help | grep -q "populate_db"; then
    echo "🌱 Populating database with sample data..."
    python manage.py populate_db
  else
    echo "ℹ️  Skipping sample data population (populate_db command not found)"
  fi
fi

echo "âœ… Setup complete! Starting application..."
echo ""

# Execute the main command (passed as arguments to this script)
exec "$@"
