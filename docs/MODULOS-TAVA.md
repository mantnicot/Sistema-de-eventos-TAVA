# Módulos TAVA — Guía funcional (español)

## Resumen

Plataforma de boletería y gestión para **@tavateatro**. Este documento describe los módulos implementados, seguridad y configuración.

---

## 1. Autenticación y registro

| Función | Ruta API | Descripción |
|---------|----------|-------------|
| Registro | `POST /api/v1/auth/register` | Crea cuenta `general`; **no** inicia sesión hasta verificar correo |
| Verificar correo | `GET /api/v1/auth/verify-email?token=...` | Activa la cuenta con enlace único (48 h) |
| Reenviar enlace | `POST /api/v1/auth/resend-verification?email=...` | Nuevo correo si expiró |
| Login | `POST /api/v1/auth/login` | Requiere correo verificado (admin exento) |
| Clave pública | `GET /api/v1/auth/public-key` | Cifrado RSA de contraseña en el navegador |

**Seguridad:** contraseñas con bcrypt; tokens de verificación hasheados; JWT para sesión.

**Correo en producción (Render):** variables opcionales:

- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`
- `EMAIL_FROM`, `FRONTEND_URL` (origen del enlace de verificación)

Sin SMTP, en logs de Render aparece la URL de verificación (útil en desarrollo).

---

## 2. Panel administrador (`/admin`)

Solo rol `admin`. Pestañas:

- **Métricas:** KPIs desde `/dashboard/kpis`
- **Eventos:** crear/editar obras, ficha teatral, estados (borrador/publicado…)
- **Usuarios:** listar y asignar roles (`seller`, `validator`, `admin`, `general`)
- **Apariencia:** URL del **video de fondo** difuminado del sitio

API eventos admin: `GET /api/v1/events/admin/all`, `POST/PATCH /api/v1/events`.

---

## 3. Eventos y ficha teatral

Cada evento incluye:

- Datos de cartelera (fecha, ciudad, imagen, trailer)
- `theatrical_details`: sinopsis, elenco, director, duración, clasificación, avisos
- Galería (`event_media`) y tipos de boleta en detalle público

Ruta pública: `/eventos/:id` — compra demo vía `POST /api/v1/tickets/purchase`.

---

## 4. Video de fondo difuminado

- Componente global `tava-hero-video` en el layout
- Configuración: `GET/PUT /api/v1/settings/appearance`
- Efecto: video a pantalla completa con `blur(28px)` y velo claro encima
- El admin cambia la URL `.mp4` desde **Panel → Apariencia**

---

## 5. Menú principal

Agrupado en: **Cartelera** · **Mi cuenta** · **Personal** (validador) · **Administración** · acciones Ingresar/Registrarse.

---

## 6. Roles

| Rol | Uso |
|-----|-----|
| `general` | Compra, perfil, colección |
| `seller` | Ventas (API preparada; UI vendedor pendiente de ampliar) |
| `validator` | Validación QR en `/validar` |
| `admin` | Panel completo |

---

## Despliegue

Tras cambios en modelos, el arranque ejecuta `schema_upgrade` (columnas/tablas nuevas). Reinicia Render y Vercel con el último commit.

**Admin seed:** `admin@tavateatro.com` / `AdminTava2026!` (correo ya verificado).
