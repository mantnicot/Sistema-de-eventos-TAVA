# TAVA — Sistema Integral de Gestión de Eventos y Boletería

Plataforma oficial para el grupo de teatro **TAVA** ([@tavateatro](https://www.instagram.com/tavateatro/)): creación de eventos, venta de boletas, diseño de silletería, validación QR, fidelización con coleccionables, marketing y reportería.

## Stack

| Capa | Tecnología |
|------|------------|
| Frontend | Angular 19+, Standalone, Signals, SCSS tema TAVA |
| Backend | Python 3.12, FastAPI, arquitectura hexagonal |
| Base de datos | PostgreSQL 16 |
| Auth | JWT + Refresh Token, roles (general, admin, validator, seller) |
| API Docs | Swagger en `/docs` |
| Contenedores | Docker Compose |

## Identidad visual

Paleta inspirada en teatro contemporáneo y la presencia de @tavateatro:

- **Burgundy / cortina** `#7B1E3A`, `#A62639`
- **Oro spotlight** `#C9A227`, glow `#E8C547`
- **Terciopelo** `#4A1942`
- **Escenario** `#0D0A0B`, `#1A0F14`
- Tipografías: Playfair Display + DM Sans
- Animaciones: spotlight pulse, curtain reveal, shimmer

## Inicio rápido

> **¿No puedes ejecutarlo en este PC?** Sube el proyecto a GitHub/GitLab y en otro equipo o servidor sigue la guía: **[docs/EJECUTAR-DESDE-REPO.md](docs/EJECUTAR-DESDE-REPO.md)**

### Requisitos

- Docker Desktop (recomendado) o Node 20+, Python 3.12+, PostgreSQL 16

### Con Docker (cualquier máquina con el repo clonado)

```bash
git clone https://github.com/mantnicot/Sistema-de-eventos-TAVA.git
cd TAVA
cp .env.example .env    # Windows: copy .env.example .env
docker compose up -d --build
```

El seed del admin demo se ejecuta solo al arrancar el backend en Docker.

- Frontend: http://localhost:4200  
- API + Swagger: http://localhost:8000/docs  
- PostgreSQL: `localhost:5432`

### Windows — un clic

Doble clic en **`TAVA-Iniciar.bat`** o **`iniciar-local.bat`** (raíz del proyecto). Levanta PostgreSQL, API y Angular en ventanas separadas.

> Si al hacer doble clic no ves ventana, usa **`TAVA-Iniciar.bat`** (fuerza que la consola permanezca abierta).

Para detener solo la base de datos: **`detener-local.bat`**.

### Entornos del frontend

| Entorno | Archivo | API |
|---------|---------|-----|
| Local | `environment.local.ts` | `http://localhost:8000/api/v1` |
| Producción | `environment.prod.ts` | `https://tava-api-1.onrender.com/api/v1` |
| Pruebas (rama `pruebas`) | `environment.pruebas.ts` | Render (frontend local) |

Ver [docs/DESARROLLO-LOCAL.md](docs/DESARROLLO-LOCAL.md).

### Desarrollo local (manual)

**Backend:**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH="src"
python scripts/seed.py
uvicorn tava.main:app --reload --port 8000
```

**Frontend:**

```powershell
cd frontend
npm install --legacy-peer-deps
npm start
```

Proxy API: `frontend/proxy.conf.json` → `http://localhost:8000`

### Credenciales demo (seed)

- **Admin:** `admin@tavateatro.com` / `AdminTava2026!`

## Estructura del proyecto

```
TAVA/
├── backend/src/tava/
│   ├── domain/          # Entidades, enums, puertos
│   ├── application/     # Casos de uso
│   ├── infrastructure/  # DB, JWT, captcha, QR
│   └── presentation/    # Routers FastAPI
├── frontend/src/app/
│   ├── core/            # Auth, API, interceptors
│   ├── features/        # Home, eventos, validación, admin…
│   ├── layout/          # Shell navegación
│   └── shared/          # Popups institucionales
├── docs/                # ER, componentes, casos de uso
├── docker-compose.yml
└── scripts/deploy.*
```

## Módulos implementados (base)

- Autenticación registro/login + refresh + captcha (modo dev sin clave)
- CRUD eventos (admin) y cartelera pública
- Escenarios, sectores, generación de sillas
- Tipos de boleta y compra con QR + hash anti-fraude
- Validación QR y aforo en tiempo real
- Coleccionables TAVA (5 eventos → boleto gratis)
- Dashboard KPIs admin
- Marketing: banners y carrusel destacados
- Popups: éxito, error, confirmación, advertencia, carga

## Pendiente / extensiones

- Pasarelas Wompi, Mercado Pago, PayU, Stripe (stubs en `.env`)
- Envío SMTP masivo y plantillas de correo
- Exportación Excel/PDF de reportes
- Escáner cámara QR (ngx-scanner) y modo offline PWA validadores
- Formularios dinámicos admin (`form_fields`)
- Integraciones WhatsApp / redes sociales

## Documentación

- [Diagrama ER](docs/er-diagram.md)
- [Diagrama de componentes](docs/component-diagram.md)
- [Casos de uso](docs/use-cases.md)

## Licencia

Proyecto privado para el grupo TAVA Teatro.
