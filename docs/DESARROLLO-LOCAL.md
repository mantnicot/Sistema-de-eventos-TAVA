# Desarrollo local — TAVA

## Requisitos

- Docker Desktop (PostgreSQL) **o** Neon + solo backend local
- Python 3.12+ (backend)
- Node.js 20+ (frontend)

## Opción A — Script Windows

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
