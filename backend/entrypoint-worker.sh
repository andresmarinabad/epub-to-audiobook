#!/bin/bash
set -e

if [ -n "$WORKER_CONCURRENCY" ]; then
    CONCURRENCY="$WORKER_CONCURRENCY"
else
    NCPU=$(nproc 2>/dev/null || echo 4)
    CONCURRENCY=$((NCPU - 2))
    [ "$CONCURRENCY" -lt 1 ] && CONCURRENCY=1
fi

echo "Starting Celery worker — concurrency: $CONCURRENCY (CPUs detected: $(nproc 2>/dev/null || echo '?'))"

# venv is in PATH at runtime — no uv needed
exec celery \
    -A audiobook.infrastructure.celery.app:celery_app \
    worker \
    --concurrency="$CONCURRENCY" \
    --loglevel=info \
    -Q chapters,celery
