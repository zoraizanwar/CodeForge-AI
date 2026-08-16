#!/bin/sh
set -e

echo "Starting CodeForge AI Container Initialization..."

# Run database migrations if executing in API mode or explicitly enabled
if [ "$SKIP_MIGRATIONS" != "true" ]; then
    echo "Running Alembic Database Migrations..."
    alembic upgrade head
    echo "Alembic Migrations Applied Successfully."
fi

# Check Container Execution Role
if [ "$CONTAINER_ROLE" = "worker" ]; then
    echo "Starting CodeForge AI Durable Job Worker Process..."
    exec python -m app.services.jobs.worker
else
    echo "Starting CodeForge AI ASGI Server (Gunicorn + Uvicorn)..."
    exec gunicorn -c gunicorn.conf.py app.main:app
fi
