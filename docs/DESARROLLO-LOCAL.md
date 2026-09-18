# Desarrollo local — TAVA

## Requisitos

- Docker Desktop (PostgreSQL) **o** Neon + solo backend local
- Python 3.12+ (backend)
- Node.js 20+ (frontend)

## Opción A — Pruebas locales (recomendado para validar sin tocar prod)

1. Doble clic en **`TAVA-PRUEBAS.bat`** (o el icono **TAVA PRUEBAS** del Escritorio).
2. Espera a que abran las ventanas API + Web.
3. Entra a http://localhost:4200 — verás la cinta verde **PRUEBAS LOCAL**.
4. Admin demo: `admin@tavateatro.com` / `AdminTava2026!`
5. Para apagar Postgres: **`TAVA-Detener-PRUEBAS.bat`**

Si aún no tienes el icono: ejecuta `scripts\crear-acceso-escritorio-pruebas.bat`.

> **No uses** `npm run start:pruebas` para esto: ese modo apunta a la API de Render (datos reales).

## Opción B — Script Windows genérico

Doble clic en `TAVA-Iniciar.bat` o `iniciar-local.bat` en la raíz del proyecto.

## Opción B — Manual

### 1. Base de datos y API

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH="src"
# Copia .env desde la raíz del proyecto (DATABASE_URL local o Neon)
python scripts/seed.py
uvicorn tava.main:app --reload --port 8000
```

API: http://localhost:8000/docs

### 2. Frontend Angular

```powershell
cd frontend
npm install --legacy-peer-deps
npm run start:local
```

Web: http://localhost:4200

El proxy (`proxy.conf.json`) no es necesario: `environment.local.ts` apunta a `http://localhost:8000/api/v1`.

## Configuraciones Angular

| Comando | Uso |
|---------|-----|
| `npm run start:local` | API local (localhost:8000) |
| `npm run start:pruebas` | API en Render (pruebas integración) |
| `npm run build` | Build producción → Render API |

## Rama `pruebas` en GitHub

```bash
git checkout pruebas
cd frontend
npm run start:pruebas
```

Útil para probar el frontend contra `https://tava-api-1.onrender.com` sin levantar el backend en tu PC.

Asegúrate de que en Render `CORS_ORIGINS` incluya `http://localhost:4200`.
