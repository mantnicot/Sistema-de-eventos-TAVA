/** Desarrollo / pruebas locales: API en Docker/uvicorn (puerto 8000). NO toca producción. */
export const environment = {
  production: false,
  /** Banner y avisos: entorno local aislado para probar */
  localPruebas: true,
  envLabel: 'PRUEBAS LOCAL',
  apiUrl: 'http://localhost:8000/api/v1',
  mediaBaseUrl: 'http://localhost:8000',
  /** hCaptcha site key; vacío = checkbox local de desarrollo */
  hcaptchaSiteKey: '',
};
