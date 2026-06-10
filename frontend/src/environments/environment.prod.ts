/** Producción: API en Render + web en Vercel. */
export const environment = {
  production: true,
  apiUrl: 'https://tava-api-1.onrender.com/api/v1',
  /** Base del API para archivos /uploads (sin /api/v1) */
  mediaBaseUrl: 'https://tava-api-1.onrender.com',
  /** Configura HCAPTCHA_SITE_KEY en Vercel; vacío = checkbox de verificación */
  hcaptchaSiteKey: 'ca06c768-73d0-445c-b7a6-47de3320110a',
};
