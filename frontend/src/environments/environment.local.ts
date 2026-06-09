/** Desarrollo local: API en Docker/uvicorn (puerto 8000). */
export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000/api/v1',
  mediaBaseUrl: 'http://localhost:8000',
  /** hCaptcha site key; vacío = checkbox local de desarrollo */
  hcaptchaSiteKey: '',
};
