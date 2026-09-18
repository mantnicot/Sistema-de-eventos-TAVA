/**
 * CUIDADO: este modo apunta a la API de Render (datos reales / producción).
 * Para probar sin afectar prod usa: npm run start:local  o  TAVA-PRUEBAS.bat
 */
export const environment = {
  production: false,
  localPruebas: false,
  envLabel: 'API REMOTA',
  apiUrl: 'https://tava-api-1.onrender.com/api/v1',
  mediaBaseUrl: 'https://tava-api-1.onrender.com',
  hcaptchaSiteKey: '',
};
