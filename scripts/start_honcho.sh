#!/bin/sh
set -eu

cd /app
/app/.venv/bin/python scripts/provision_db.py
# Upstream migrations create vector(1536). Configure the selected local model
# before the API validates the schema. The upstream script refuses to change
# populated embedding tables and does nothing when dimensions already match.
/app/.venv/bin/python scripts/configure_embeddings.py --yes
exec /app/.venv/bin/fastapi run --host 0.0.0.0 --workers "${API_WORKERS:-1}" src/main.py
