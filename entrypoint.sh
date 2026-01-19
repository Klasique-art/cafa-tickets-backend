#!/bin/bash

echo "Waiting for PostgreSQL..."
while ! nc -z db 5432; do
  sleep 0.5
done
echo "PostgreSQL started"

python manage.py migrate --noinput

# python manage.py createsuperuser --noinput || true

exec "$@"