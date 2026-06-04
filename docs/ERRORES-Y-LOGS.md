# Errores y logs — TAVA

## Respuestas de la API

Todas las errores JSON incluyen:

```json
{
  "error_type": "user | system",
  "code": "AUTH_INVALID",
  "message": "Texto para el usuario",
  "status": 401
}
```

| error_type | Significado | Ejemplo |
|------------|-------------|---------|
| `user` | El usuario puede corregir algo | Contraseña incorrecta, email ya registrado |
| `system` | Fallo del servidor / infra | Base de datos caída, error 500 |

## Códigos de login

| code | HTTP | Mensaje típico |
|------|------|----------------|
| `AUTH_INVALID` | 401 | Credenciales inválidas |
| `AUTH_INACTIVE` | 401 | Usuario inactivo |
| `DATABASE_ERROR` | 503 | No hay conexión a Neon |
| `CAPTCHA_INVALID` | 400 | Captcha (si se configura) |

## Logs en Render

Dashboard → tu servicio → **Logs**. Busca:

- `Login exitoso` — OK
- `Login rechazado (usuario)` — contraseña/email mal (no es bug)
- `Login falló (base de datos)` — revisar `DATABASE_URL` y Neon
- `Login falló (sistema)` — error inesperado, ver traceback

## Health checks

- `GET /health` — API viva
- `GET /health/db` — prueba conexión a PostgreSQL

## Frontend (consola F12)

Los errores se registran como:

- `[TAVA] login: usuario ...` — advertencia amarilla
- `[TAVA] login: sistema ...` — error rojo
- `[TAVA] login: status=0` — CORS o API apagada

## CORS en Render

`CORS_ORIGINS` con **comas**:

```text
http://localhost:4200,https://sistema-de-eventos-tava.vercel.app
```

También se aceptan subdominios `*.vercel.app` por regex.
