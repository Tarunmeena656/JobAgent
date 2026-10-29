#!/bin/sh
# container entrypoint: create tables, optionally seed the demo accounts, then serve
set -e
python scripts/init_db.py
if [ "$SEED_DEMO" = "1" ]; then
  python scripts/seed.py
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
