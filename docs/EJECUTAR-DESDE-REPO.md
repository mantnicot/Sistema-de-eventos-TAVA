# Cómo ejecutar TAVA después de subirlo a un repositorio

No necesitas el PC donde se creó el proyecto. En **cualquier otro equipo** (o en la nube) solo clonas el repo y sigues una de estas opciones.

---

## Opción 1 — Docker (recomendada)

La más simple: un solo comando levanta base de datos, API y web.

### Requisitos en el equipo nuevo

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac) o Docker Engine (Linux)
- [Git](https://git-scm.com/)

### Pasos

```bash
# 1. Clonar
git clone https://github.com/TU_USUARIO/TU_REPO.git
cd TU_REPO

# 2. Variables de entorno
cp .env.example .env
# Edita .env y cambia JWT_SECRET_KEY y POSTGRES_PASSWORD en producción

# 3. Levantar todo (primera vez tarda: descarga imágenes y compila)
docker compose up -d --build

# 4. Cargar datos demo (admin + evento de ejemplo) — solo la primera vez
docker compose exec backend python scripts/seed.py
```

### Abrir en el navegador

| Servicio | URL |
|----------|-----|
| **Aplicación web** | http://localhost:4200 |
| **API / Swagger** | http://localhost:8000/docs |
| **Health API** | http://localhost:8000/health |

**Usuario admin demo:** `admin@tavateatro.com` / `AdminTava2026!`

### Comandos útiles

```bash
# Ver logs
docker compose logs -f

# Detener
docker compose down

# Detener y borrar base de datos
docker compose down -v
```

---

## Opción 2 — Sin Docker (desarrollo)

Útil si instalas Python, Node y PostgreSQL a mano.

### Requisitos

- Python 3.12+
- Node.js 20+
- PostgreSQL 16 (local o remoto)

### Pasos

```bash
git clone https://github.com/TU_USUARIO/TU_REPO.git
cd TU_REPO
cp .env.example .env
```

Ajusta en `.env` la línea `DATABASE_URL` con tu usuario, contraseña y host de PostgreSQL.

**Terminal 1 — API:**

```bash
cd backend
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -r requirements.txt
export PYTHONPATH=src          # Mac/Linux
# Windows PowerShell:  $env:PYTHONPATH="src"

python scripts/seed.py
uvicorn tava.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend:**

```bash
cd frontend
npm install --legacy-peer-deps
npm start
```

- Web: http://localhost:4200  
- API: http://localhost:8000/docs  

---

## Opción 3 — Servidor en la nube (VPS)

Mismo flujo que Docker en un Linux (DigitalOcean, AWS EC2, Azure VM, etc.):

```bash
ssh usuario@tu-servidor
sudo apt update && sudo apt install -y git docker.io docker-compose-plugin
git clone https://github.com/TU_USUARIO/TU_REPO.git
cd TU_REPO
cp .env.example .env
nano .env   # contraseñas y JWT_SECRET_KEY seguros
sudo docker compose up -d --build
sudo docker compose exec backend python scripts/seed.py
```

Abre en el firewall los puertos **80** o **4200** (frontend) y **8000** (API), o pon un dominio con **Nginx + HTTPS** delante.

---

## Opción 4 — GitHub Codespaces / dev container

Si el repo está en GitHub:

1. Sube el código a GitHub.
2. En el repositorio: **Code → Codespaces → Create codespace**.
3. Dentro del codespace, en la terminal:

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec backend python scripts/seed.py
```

4. Codespaces te da URLs públicas temporales para los puertos reenviados (pestaña **Ports**).

---

## Qué subir al repositorio

**Sí subir:**

- Todo el código (`backend/`, `frontend/`, `docs/`, `docker-compose.yml`, scripts)
- `.env.example` (plantilla sin secretos)

**No subir:**

- `.env` (secretos reales)
- `backend/.venv/`
- `frontend/node_modules/`
- `frontend/dist/`

El `.gitignore` del proyecto ya excluye eso.

### Crear el repo y subir (desde cualquier PC con Git)

```bash
cd ruta/al/proyecto/TAVA
git init
git add .
git commit -m "Initial commit: plataforma TAVA"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/TAVA.git
git push -u origin main
```

---

## Resumen rápido

| Dónde lo ejecutas | Qué necesitas | Comando principal |
|-------------------|---------------|-------------------|
| Otro PC Windows/Mac | Docker Desktop + Git | `docker compose up -d --build` |
| Otro PC sin Docker | Python + Node + PostgreSQL | Ver Opción 2 |
| Servidor Linux | Docker + Git | Igual que Opción 1 |
| GitHub Codespaces | Cuenta GitHub | Codespace + Docker |

En todos los casos, después del primer arranque ejecuta **una vez** el seed para tener el usuario administrador.
