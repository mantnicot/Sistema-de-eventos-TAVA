import { HttpErrorResponse } from '@angular/common/http';

export type TavaErrorKind = 'user' | 'system' | 'network';

export interface ParsedHttpError {
  kind: TavaErrorKind;
  title: string;
  message: string;
  code?: string;
  status?: number;
  /** Para consola / soporte */
  logLine: string;
}

interface ApiErrorBody {
  error_type?: 'user' | 'system';
  code?: string;
  message?: string;
  status?: number;
  detail?: string | ApiErrorBody;
}

function extractBody(err: HttpErrorResponse): ApiErrorBody | null {
  const body = err.error;
  if (!body || typeof body !== 'object') return null;
  return body as ApiErrorBody;
}

function messageFromBody(body: ApiErrorBody | null, fallback: string): string {
  if (!body) return fallback;
  if (typeof body.message === 'string') return body.message;
  if (typeof body.detail === 'string') return body.detail;
  if (body.detail && typeof body.detail === 'object' && typeof body.detail.message === 'string') {
    return body.detail.message;
  }
  return fallback;
}

/** Clasifica errores HTTP: usuario vs sistema vs red/CORS. */
export function parseHttpError(err: unknown, context = 'operacion'): ParsedHttpError {
  if (!(err instanceof HttpErrorResponse)) {
    return {
      kind: 'system',
      title: 'No pudimos terminar',
      message: 'Algo no salio como esperabamos. Intenta de nuevo en un momento.',
      logLine: `[TAVA] ${context}: error no HTTP`,
    };
  }

  const status = err.status;
  const body = extractBody(err);
  const apiType = body?.error_type;
  const code = body?.code;
  const apiMessage = messageFromBody(body, '');

  if (status === 0 && (err.statusText === 'Timeout' || code === 'LOGIN_TIMEOUT')) {
    return {
      kind: 'network',
      title: 'El servidor se demoró mucho',
      message: apiMessage || 'El servidor se demoró mucho, vuelve a intentarlo.',
      code: code ?? 'TIMEOUT',
      status: 0,
      logLine: `[TAVA] ${context}: timeout ${err.url}`,
    };
  }

  if (status === 0) {
    const corsHint = err.message?.toLowerCase().includes('failed') || err.statusText === 'Unknown Error';
    return {
      kind: 'network',
      title: 'No logramos conectar',
      message: corsHint
        ? 'El servidor puede estar iniciando. Espera unos segundos y vuelve a intentar.'
        : 'Revisa tu conexion a internet y prueba nuevamente.',
      code: 'NETWORK_ERROR',
      status: 0,
      logLine: `[TAVA] ${context}: status=0 ${err.url}`,
    };
  }

  if (apiType === 'user' || status === 401 || status === 403 || status === 404 || status === 422) {
    const msg =
      apiMessage ||
      (status === 401 ? 'El correo o la contrasena no coinciden.' : 'Revisa la informacion e intenta de nuevo.');
    return {
      kind: 'user',
      title: status === 401 ? 'No pudimos ingresar' : 'Revisa estos datos',
      message: msg,
      code: code ?? `HTTP_${status}`,
      status,
      logLine: `[TAVA] ${context}: usuario status=${status} code=${code} msg=${msg}`,
    };
  }

  if (status === 429) {
    return {
      kind: 'system',
      title: 'Demasiados intentos',
      message: 'Hiciste varios intentos seguidos. Espera un minuto y vuelve a probar.',
      code: 'RATE_LIMIT',
      status,
      logLine: `[TAVA] ${context}: rate limit`,
    };
  }

  if (status === 503 || apiType === 'system' || status >= 500) {
    const msg =
      apiMessage ||
      (status === 503
        ? 'El servicio esta tardando en responder. Espera un momento e intenta otra vez.'
        : 'Tuvimos un problema interno. Tu solicitud no se completo.');
    return {
      kind: 'system',
      title: 'Estamos revisando tras bambalinas',
      message: msg,
      code: code ?? `HTTP_${status}`,
      status,
      logLine: `[TAVA] ${context}: sistema status=${status} code=${code} msg=${msg}`,
    };
  }

  return {
    kind: 'user',
    title: 'No se pudo completar',
    message: apiMessage || err.message || 'Intenta de nuevo en un momento.',
    code,
    status,
    logLine: `[TAVA] ${context}: status=${status}`,
  };
}
