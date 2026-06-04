#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example — update secrets before production."
fi

docker compose build
docker compose up -d

echo "TAVA stack running:"
echo "  Frontend: http://localhost:4200"
echo "  API/Swagger: http://localhost:8000/docs"
echo "  PostgreSQL: localhost:5432"
