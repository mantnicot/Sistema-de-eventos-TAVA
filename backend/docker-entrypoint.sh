#!/bin/sh
set -e
# Bootstrap corre en el lifespan de FastAPI — evitar doble ejecución en cold start.
echo "TAVA API - iniciando uvicorn..."
exec uvicorn tava.main:app --host 0.0.0.0 --port 8000
