#!/bin/sh
set -e
echo "TAVA API - ejecutando seed si aplica..."
python scripts/seed.py || echo "Seed omitido o ya aplicado."
exec uvicorn tava.main:app --host 0.0.0.0 --port 8000
