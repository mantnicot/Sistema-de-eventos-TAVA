export type TavoActionId =
  | 'menu'
  | 'buy'
  | 'buy_how'
  | 'buy_cartelera'
  | 'create'
  | 'create_steps'
  | 'create_review'
  | 'tickets'
  | 'tickets_claim'
  | 'tickets_mine'
  | 'faq'
  | 'faq_payment'
  | 'faq_email'
  | 'faq_money'
  | 'whatsapp'
  | 'bye';

export interface TavoButton {
  id: TavoActionId;
  label: string;
  route?: string;
  fragment?: string;
  external?: boolean;
}

export interface TavoMessage {
  id: string;
  from: 'tavo' | 'user';
  text: string;
  buttons?: TavoButton[];
}

const WHATSAPP_BASE =
  'https://wa.me/573003268095?text=';

export function buildWhatsappUrl(doubt: string): string {
  const msg =
    `Hola TAVA Teatro, vengo desde el asistente Tavo del sistema.\n\n` +
    `Mi duda: ${doubt.trim() || 'Necesito ayuda con la plataforma.'}`;
  return WHATSAPP_BASE + encodeURIComponent(msg);
}

export const TAVO_WELCOME =
  'Bienvenido a TAVA Teatro. ¡Hola! Soy Tavo 🎭, asistente de TAVA. ¿Buscas boletas o quieres publicar tu evento?';

export const TAVO_SCOPE =
  'Solo te ayudo con: comprar boletas, reclamar o ver tus boletas, crear/publicar eventos, el flujo de aprobación y dudas generales de la plataforma. Si necesitas otra cosa, te paso a WhatsApp con tu duda.';

const MAIN_BUTTONS: TavoButton[] = [
  { id: 'buy', label: '🎟️ Comprar boletas' },
  { id: 'create', label: '📝 Crear / publicar evento' },
  { id: 'tickets', label: '🎫 Mis boletas / reclamar' },
  { id: 'faq', label: '❓ FAQ general' },
  { id: 'whatsapp', label: '💬 Hablar por WhatsApp' },
];

function msg(text: string, buttons?: TavoButton[]): Omit<TavoMessage, 'id' | 'from'> {
  return { text, buttons };
}

/** Resuelve una acción de botón del menú guiado. */
export function resolveTavoAction(action: TavoActionId): {
  reply: Omit<TavoMessage, 'id' | 'from'>;
  navigateTo?: string;
  fragment?: string;
  openWhatsapp?: string;
} {
  switch (action) {
    case 'menu':
      return {
        reply: msg(TAVO_WELCOME, MAIN_BUTTONS),
      };

    case 'buy':
      return {
        reply: msg(
          'Perfecto. Puedes ver la cartelera y elegir tu función. Te guío paso a paso.',
          [
            { id: 'buy_cartelera', label: 'Ver cartelera', route: '/eventos' },
            { id: 'buy_how', label: '¿Cómo compro?' },
            { id: 'menu', label: '← Menú' },
            { id: 'whatsapp', label: 'WhatsApp' },
          ]
        ),
      };

    case 'buy_how':
      return {
        reply: msg(
          'Así compras en TAVA:\n1) Entra a la cartelera.\n2) Abre el evento.\n3) Elige tipo de boleta y paga con Wompi.\n4) Recibes PDF / QR por correo o en Mis boletas.\nNo invento precios: siempre mira el valor en la ficha del evento.',
          [
            { id: 'buy_cartelera', label: 'Ir a cartelera', route: '/eventos' },
            { id: 'tickets_claim', label: 'Reclamar código', route: '/perfil', fragment: 'reclamar' },
            { id: 'menu', label: '← Menú' },
            { id: 'whatsapp', label: 'WhatsApp' },
          ]
        ),
      };

    case 'buy_cartelera':
      return {
        reply: msg('Te llevo a la cartelera. Cuando elijas una obra, compra desde su ficha 🎟️', MAIN_BUTTONS),
        navigateTo: '/eventos',
      };

    case 'create':
      return {
        reply: msg(
          'Para publicar necesitas rol de organizador. Creas tu evento, lo envías a revisión y el admin global decide si aparece en cartelera. Yo no puedo aprobar eventos.',
          [
            { id: 'create_steps', label: 'Pasos para crear' },
            { id: 'create_review', label: '¿Qué es la revisión?' },
            { id: 'menu', label: '← Menú' },
            { id: 'whatsapp', label: 'WhatsApp' },
          ]
        ),
      };

    case 'create_steps':
      return {
        reply: msg(
          'Pasos claros:\n1) Inicia sesión.\n2) Ve a Gestionar eventos / Panel.\n3) Completa datos, aforo y boletería.\n4) Guarda y pulsa «Enviar a revisión».\n5) Espera aprobación del admin. Luego puede mostrarse en cartelera.',
          [
            { id: 'create_steps', label: 'Ir al panel de eventos', route: '/admin' },
            { id: 'create_review', label: 'Flujo de aprobación' },
            { id: 'menu', label: '← Menú' },
            { id: 'whatsapp', label: 'WhatsApp' },
          ]
        ),
      };

    case 'create_review':
      return {
        reply: msg(
          'Flujo de aprobación:\n• Organizador crea y envía a revisión.\n• Queda pendiente (no en cartelera aún).\n• El admin global aprueba o rechaza.\n• Solo eventos aprobados y visibles salen en cartelera.\nNo prometo plazos ni resultados de aprobación.',
          [
            { id: 'create_steps', label: 'Cómo crear' },
            { id: 'menu', label: '← Menú' },
            { id: 'whatsapp', label: 'WhatsApp' },
          ]
        ),
      };

    case 'tickets':
      return {
        reply: msg(
          'Tus boletas viven en tu perfil. Si te dieron un código de reclamo, también puedes pegarlo ahí.',
          [
            { id: 'tickets_mine', label: 'Ver mis boletas', route: '/perfil' },
            { id: 'tickets_claim', label: 'Reclamar código', route: '/perfil', fragment: 'reclamar' },
            { id: 'menu', label: '← Menú' },
            { id: 'whatsapp', label: 'WhatsApp' },
          ]
        ),
      };

    case 'tickets_mine':
      return {
        reply: msg('Te abro Mis boletas. Ahí descargas PDF y ves tus QR.', MAIN_BUTTONS),
        navigateTo: '/perfil',
      };

    case 'tickets_claim':
      return {
        reply: msg(
          'En Perfil → Reclamar código pega el código del correo o de la taquilla. Si no tienes cuenta, regístrate primero.',
          MAIN_BUTTONS
        ),
        navigateTo: '/perfil',
        fragment: 'reclamar',
      };

    case 'faq':
      return {
        reply: msg('Elige un tema. Si no está en la lista, WhatsApp con tu duda.', [
          { id: 'faq_payment', label: 'Pagos Wompi' },
          { id: 'faq_email', label: 'No llegó el correo' },
          { id: 'faq_money', label: 'Dinero / ventas del evento' },
          { id: 'menu', label: '← Menú' },
          { id: 'whatsapp', label: 'WhatsApp' },
        ]),
      };

    case 'faq_payment':
      return {
        reply: msg(
          'El pago se hace con Wompi en la ficha del evento. Si el pago falla, revisa el correo del banco o reintenta. No confirmo estados inventados: mira Compra/resultado o Mis boletas.',
          [
            { id: 'buy_cartelera', label: 'Ir a cartelera', route: '/eventos' },
            { id: 'faq', label: '← FAQ' },
            { id: 'whatsapp', label: 'WhatsApp' },
          ]
        ),
      };

    case 'faq_email':
      return {
        reply: msg(
          'Revisa spam. También puedes ver/descargar boletas en Mis boletas si iniciaste sesión. Si compraste sin cuenta, usa el código de reclamo del correo.',
          [
            { id: 'tickets_mine', label: 'Mis boletas', route: '/perfil' },
            { id: 'faq', label: '← FAQ' },
            { id: 'whatsapp', label: 'WhatsApp' },
          ]
        ),
      };

    case 'faq_money':
      return {
        reply: msg(
          'El admin global ve métricas y ventas globales. Un organizador gestiona sus eventos; el detalle de liquidaciones lo confirma el equipo TAVA. No invento montos ni comisiones aquí.',
          [
            { id: 'faq', label: '← FAQ' },
            { id: 'whatsapp', label: 'WhatsApp con mi duda' },
          ]
        ),
      };

    case 'whatsapp':
      return {
        reply: msg(
          'Te abro WhatsApp con un mensaje listo: indica que vienes de Tavo. ¡Gracias por escribirnos! 🎭',
          MAIN_BUTTONS
        ),
        openWhatsapp: buildWhatsappUrl('Necesito ayuda con la plataforma TAVA.'),
      };

    case 'bye':
      return {
        reply: msg(
          'Gracias por conversar conmigo. Cuando quieras, aquí estaré. ¡Que disfrutes la función! 🎭',
          MAIN_BUTTONS
        ),
      };

    default:
      return {
        reply: msg(TAVO_SCOPE, MAIN_BUTTONS),
      };
  }
}

/** Interpreta texto libre del usuario (MVP por palabras clave). */
export function resolveTavoFreeText(raw: string): {
  reply: Omit<TavoMessage, 'id' | 'from'>;
  navigateTo?: string;
  fragment?: string;
  openWhatsapp?: string;
} {
  const t = raw.trim().toLowerCase();
  if (!t) {
    return { reply: msg('Cuéntame tu duda o elige un botón.', MAIN_BUTTONS) };
  }

  if (/hola|buenas|hey|saludos/.test(t)) {
    return resolveTavoAction('menu');
  }
  if (/gracias|chao|adi[oó]s|hasta luego/.test(t)) {
    return resolveTavoAction('bye');
  }
  if (/whatsapp|humano|asesor|hablar con/.test(t)) {
    return {
      reply: msg('Claro. Te paso a WhatsApp con tu mensaje.', MAIN_BUTTONS),
      openWhatsapp: buildWhatsappUrl(raw),
    };
  }
  if (/comprar|boleta|ticket|cartelera|precio|cu[aá]nto/.test(t)) {
    if (/precio|cu[aá]nto/.test(t)) {
      return {
        reply: msg(
          'No invento precios. Entra a la ficha del evento en cartelera y verás el valor real de cada tipo de boleta.',
          [
            { id: 'buy_cartelera', label: 'Ver cartelera', route: '/eventos' },
            { id: 'buy_how', label: 'Cómo comprar' },
            { id: 'whatsapp', label: 'WhatsApp' },
            { id: 'menu', label: '← Menú' },
          ]
        ),
      };
    }
    return resolveTavoAction('buy');
  }
  if (/crear|publicar|organizador|revisi[oó]n|aprobar|evento/.test(t) && !/boleta/.test(t)) {
    if (/aprobar|revisi[oó]n|pendiente/.test(t)) {
      return resolveTavoAction('create_review');
    }
    return resolveTavoAction('create');
  }
  if (/reclamar|c[oó]digo|mis boletas|qr|pdf/.test(t)) {
    return resolveTavoAction('tickets');
  }
  if (/pago|wompi|correo|email|dinero|venta|comisi[oó]n/.test(t)) {
    return resolveTavoAction('faq');
  }

  return {
    reply: msg(
      `${TAVO_SCOPE}\n\nPuedo reenviar tu duda a WhatsApp para que el equipo te ayude.`,
      [
        { id: 'menu', label: 'Ver opciones' },
        { id: 'whatsapp', label: 'Enviar esta duda por WhatsApp' },
      ]
    ),
    // Guardamos la duda en el botón vía flujo del componente
  };
}

export function isWhatsappHandoffIntent(text: string): boolean {
  return /whatsapp|enviar esta duda/i.test(text);
}
