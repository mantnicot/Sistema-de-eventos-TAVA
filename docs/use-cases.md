# Casos de Uso — TAVA

## Actores

- **Usuario general** — compra, favoritos, coleccionables, reseñas
- **Vendedor** — venta, reservas, enlaces, comisiones
- **Validador** — escaneo QR, aforo, ingreso manual
- **Administrador** — control total del ciclo de vida del evento

## UC-01 Registro con captcha

1. El usuario completa el formulario dinámico.
2. El sistema valida captcha y datos.
3. Se crea cuenta con rol `general` y se emiten JWT + refresh token.

## UC-02 Compra de boletas

1. Usuario selecciona evento publicado.
2. Elige tipo de boleta y sillas (si hay mapa).
3. Acepta términos legales y pasa captcha.
4. Se crea orden `pendiente`, boletas con QR único y hash de seguridad.
5. Pasarela confirma pago → estado `pagado`, correo de confirmación.
6. Se otorga lámina coleccionable; al 5.º evento → boleto gratis.

## UC-03 Validación en puerta

1. Validador abre vista móvil y escanea QR.
2. Sistema verifica token, hash, estado del evento y uso previo.
3. Respuesta: autorizado / ya utilizada / evento no habilitado / inválida.
4. Actualiza aforo en tiempo real.

## UC-04 Crear evento (admin)

1. Admin crea evento en borrador con galería y trailer.
2. Configura escenario, sectores y tipos de boleta.
3. Publica → estado `publicado`, visible en carrusel.

## UC-05 Reportes

1. Admin solicita exportación ventas/asistencia.
2. Sistema genera Excel o PDF desde agregados del dashboard.

## UC-06 Gestión de formularios dinámicos

1. Admin crea/edita campos en `form_fields` por `form_key`.
2. El frontend renderiza campos según configuración API.
