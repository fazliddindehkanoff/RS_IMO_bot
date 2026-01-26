#!/bin/bash
set -e

# Wait for database to be ready (for SQLite, just ensure directory exists)
mkdir -p /app/data

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files (if not already done)
echo "Collecting static files..."
python manage.py collectstatic --noinput || true

# Execute the main command
exec "$@"
