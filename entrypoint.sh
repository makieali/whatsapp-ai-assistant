#!/usr/bin/env sh
set -e

# Apply database migrations before serving (no-op when DATABASE_URL is unset and
# the in-process store is used). Safe to run on every boot — Alembic only
# applies what's missing.
if [ -n "$DATABASE_URL" ]; then
  echo "Running database migrations..."
  alembic upgrade head
fi

exec "$@"
