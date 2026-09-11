export type TavoActionId =
  | 'menu'
  | 'buy'
  | 'buy_how'
  | 'buy_cartelera'
  | 'events_info'
  | 'create'
  | 'create_steps'
  | 'create_review'
  | 'create_commission'
  | 'wa_validate'
  | 'settlement'
  | 'validate_entry'
  | 'sell_help'
  | 'admin_panel'
  | 'tickets'
  | 'tickets_claim'
  | 'tickets_mine'
  | 'faq'
  | 'faq_payment'
  | 'faq_email'
  | 'faq_money'
  | 'whatsapp'
  | 'bye';

export type TavoRole =
  | 'guest'
  | 'general'
  | 'organizer'
  | 'validator'
  | 'seller'
  | 'platform_admin';

export interface TavoUserContext {
  role: TavoRole;
  loggedIn: boolean;
}

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

/** Datos mínimos de cartelera para responder en el chat. */
export interface TavoEventBrief {
  id: string;
  name: string;
  description?: string;
  event_date: string;
  event_time: string;
  city: string;
  address: string;
  category?: string;
  tickets_available?: number;
  ticket_types?: { name: string; price: number }[];
}

export interface TavoResolveResult {
  reply: Omit<TavoMessage, 'id' | 'from'>;
  navigateTo?: string;
  fragment?: string;
  openWhatsapp?: string;
  fetchEventId?: string;
}

const WHATSAPP_BASE = 'https://wa.me/573003268095?text=';

export function buildWhatsappUrl(doubt: string): string {
  const msg =
    `Hola TAVA Teatro, vengo desde el asistente Tavo del sistema.\n\n` +
    `Mi duda: ${doubt.trim() || 'Necesito ayuda con la plataforma.'}`;
  return WHATSAPP_BASE + encodeURIComponent(msg);
}

export function welcomeForRole(role: TavoRole): string {
  switch (role) {
    case 'platform_admin':
      return 'Hola, admin 🎭 Soy Tavo. Puedo ayudarte con revisión, liquidaciones, cartelera y dudas generales.';
    case 'organizer':
      return 'Hola, organizador 🎭 Soy Tavo. Te guío con crear eventos, WhatsApp, comisión y liquidación. También tienes opciones generales.';
    case 'validator':
      return 'Hola, validador 🎭 Soy Tavo. Te ayudo con el ingreso de asistentes y también con cartelera y dudas generales.';
    case 'seller':
      return 'Hola, taquilla 🎭 Soy Tavo. Te oriento en ventas y también en cartelera / dudas generales.';
    case 'general':
      return '¡Hola! Soy Tavo 🎭, asistente de TAVA. ¿Buscas boletas o info de un evento?';
    default:
      return 'Bienvenido a TAVA Teatro. ¡Hola! Soy Tavo 🎭. ¿Buscas boletas o info de un evento?';
  }
}

export const TAVO_SCOPE_CLIENT =
  'Puedo ayudarte con: cartelera, comprar boletas (muchas veces por WhatsApp), reclamar o ver tus boletas y dudas generales. Si necesitas otra cosa, te paso a WhatsApp.';

export const TAVO_SCOPE_STAFF =
  'Según tu rol te oriento en panel, ventas WhatsApp, comisión/liquidación o validación de ingreso. También tienes opciones generales: cartelera, FAQ y WhatsApp.';

/** Opciones generales (todos los roles). */
function generalButtons(ctx: TavoUserContext): TavoButton[] {
  const buttons: TavoButton[] = [
    { id: 'events_info', label: '🎭 Ver eventos' },
    { id: 'faq', label: '❓ FAQ general' },
    { id: 'whatsapp', label: '💬 Hablar por WhatsApp' },
  ];
  if (ctx.loggedIn) {
    buttons.unshift({ id: 'tickets', label: '🎫 Mis boletas / reclamar' });
  }
  return buttons;
}

/** Menú principal según rol. */
export function menuButtons(ctx: TavoUserContext): TavoButton[] {
  const shared = generalButtons(ctx);
  switch (ctx.role) {
    case 'platform_admin':
      return [
        { id: 'admin_panel', label: '🛠️ Panel admin', route: '/admin' },
        { id: 'create_review', label: '📋 Revisión / cartelera' },
        { id: 'settlement', label: '💰 Liquidación comisión' },
        { id: 'create', label: '📝 Crear / publicar evento' },
        { id: 'buy', label: '🎟️ Comprar boletas' },
        ...shared,
      ];
    case 'organizer':
      return [
        { id: 'create', label: '📝 Crear / publicar evento' },
        { id: 'wa_validate', label: '✅ Validar pagos WhatsApp' },
        { id: 'create_commission', label: '📄 Comisión y contrato' },
        { id: 'settlement', label: '💰 Liquidación T-1h' },
        { id: 'admin_panel', label: '🛠️ Ir al panel', route: '/admin' },
        { id: 'buy', label: '🎟️ Comprar boletas' },
        ...shared,
      ];
    case 'validator':
      return [
        { id: 'validate_entry', label: '🚪 Validar ingreso' },
        { id: 'settlement', label: '💰 ¿Por qué está bloqueado?' },
        { id: 'buy', label: '🎟️ Comprar boletas' },
        ...shared,
      ];
    case 'seller':
      return [
        { id: 'sell_help', label: '🧾 Vender en taquilla' },
        { id: 'buy', label: '🎟️ Comprar boletas' },
        ...shared,
      ];
    case 'general':
    case 'guest':
    default:
      return [
        { id: 'buy', label: '🎟️ Comprar boletas' },
        ...shared,
      ];
  }
}

function msg(text: string, buttons?: TavoButton[]): Omit<TavoMessage, 'id' | 'from'> {
  return { text, buttons };
}

function normalize(s: string): string {
  return s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function formatDate(date: string): string {
  try {
    const d = new Date(date.includes('T') ? date : `${date}T12:00:00`);
    return d.toLocaleDateString('es-CO', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return date;
  }
}

function formatPrice(n: number): string {
  return new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    maximumFractionDigits: 0,
  }).format(n);
}

export function formatEventInfo(ev: TavoEventBrief, withPrices = false): string {
  const lines = [
    `🎭 ${ev.name}`,
    `📅 ${formatDate(ev.event_date)} · ${ev.event_time || '—'}`,
    `📍 ${ev.city}${ev.address ? ` · ${ev.address}` : ''}`,
  ];
  if (ev.category) lines.push(`🏷️ ${ev.category}`);
  if (typeof ev.tickets_available === 'number') {
    lines.push(`🎟️ Disponibles: ${ev.tickets_available}`);
  }
  if (ev.description?.trim()) {
    const desc = ev.description.trim();
    lines.push(desc.length > 180 ? `${desc.slice(0, 177)}…` : desc);
  }
  if (withPrices && ev.ticket_types?.length) {
    lines.push('💰 Boletas:');
    for (const tt of ev.ticket_types) {
      lines.push(`  • ${tt.name}: ${formatPrice(tt.price)}`);
    }
  }
  return lines.join('\n');
}

export function findMatchingEvents(query: string, events: TavoEventBrief[]): TavoEventBrief[] {
  const q = normalize(query);
  if (!q || !events.length) return [];

  const scored = events
    .map((ev) => {
      const name = normalize(ev.name);
      const city = normalize(ev.city || '');
      let score = 0;
      if (name && q.includes(name)) score += 100;
      if (name && name.includes(q)) score += 80;
      const tokens = q.split(' ').filter((t) => t.length > 2);
      for (const t of tokens) {
        if (name.includes(t)) score += 12;
        if (city.includes(t)) score += 6;
      }
      return { ev, score };
    })
    .filter((x) => x.score >= 12)
    .sort((a, b) => b.score - a.score);

  return scored.slice(0, 3).map((x) => x.ev);
}

export function listCarteleraSummary(events: TavoEventBrief[], limit = 5): string {
  if (!events.length) {
    return 'Ahora mismo no hay eventos cargados en cartelera. Puedes abrir la cartelera para ver novedades.';
  }
  const slice = events.slice(0, limit);
  const lines = slice.map(
    (ev, i) => `${i + 1}. ${ev.name} — ${formatDate(ev.event_date)} · ${ev.city}`
  );
  const more = events.length > limit ? `\n…y ${events.length - limit} más en cartelera.` : '';
  return `Cartelera actual (${events.length}):\n${lines.join('\n')}${more}`;
}

function isStaff(role: TavoRole): boolean {
  return role === 'platform_admin' || role === 'organizer' || role === 'validator' || role === 'seller';
}

function isCapabilityQuestion(t: string): boolean {
  return (
    /\b(puedes|podes|sabes|haces|eres capaz|tu puedes|tavo puede|el chatbot|asistente)\b/.test(t) ||
    /\b(confirmas|inventas|apruebas|das precios|das valores)\b/.test(t)
  );
}

function capabilityReply(ctx: TavoUserContext): TavoResolveResult {
  const scope = isStaff(ctx.role) ? TAVO_SCOPE_STAFF : TAVO_SCOPE_CLIENT;
  return {
    reply: msg(
      `${scope}\n\n` +
        'Si preguntas si yo apruebo eventos o confirmo un pago: eso lo hace el admin/organizador en el panel, no el chat.',
      menuButtons(ctx)
    ),
  };
}

function denyStaffAction(ctx: TavoUserContext, hint: string): TavoResolveResult {
  return {
    reply: msg(
      `${hint}\n\nCon tu sesión actual te muestro el menú de cliente / opciones generales.`,
      menuButtons(ctx)
    ),
  };
}

/** Resuelve una acción de botón del menú guiado. */
export function resolveTavoAction(
  action: TavoActionId,
  events: TavoEventBrief[] = [],
  ctx: TavoUserContext = { role: 'guest', loggedIn: false }
): TavoResolveResult {
  const menu = () => menuButtons(ctx);

  switch (action) {
    case 'menu':
      return { reply: msg(welcomeForRole(ctx.role), menu()) };

    case 'buy':
      return {
        reply: msg(
          'Perfecto. Entra a la cartelera, elige la función y el tipo de boleta. En muchos eventos el pago se coordina por WhatsApp; cuando el organizador valide el dinero en TAVA, recibes correo y código de boleta.',
          [
            { id: 'buy_cartelera', label: 'Ver cartelera', route: '/eventos' },
            { id: 'events_info', label: 'Info de eventos aquí' },
            { id: 'buy_how', label: '¿Cómo compro?' },
            { id: 'menu', label: '← Menú' },
            { id: 'whatsapp', label: 'WhatsApp' },
          ]
        ),
      };

    case 'buy_how':
      return {
        reply: msg(
          'Así compras en TAVA:\n' +
            '1) Entra a la cartelera y abre el evento.\n' +
            '2) Elige tipo y cantidad (inicia sesión si te lo pide).\n' +
            '3) Si el evento es por WhatsApp: se abre un mensaje con tu pedido; pagas como te indiquen.\n' +
            '4) El administrador del evento valida el pago en el panel.\n' +
            '5) Recibes PDF / QR por correo o en Mis boletas.\n' +
            'Los precios están en la ficha de cada evento.',
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
        reply: msg('Te llevo a la cartelera. Cuando elijas una obra, sigue la compra desde su ficha 🎟️', menu()),
        navigateTo: '/eventos',
      };

    case 'events_info':
      return {
        reply: msg(
          `${listCarteleraSummary(events)}\n\nEscribe el nombre de una obra para ver más detalle, o abre la cartelera.`,
          [
            { id: 'buy_cartelera', label: 'Abrir cartelera', route: '/eventos' },
            { id: 'menu', label: '← Menú' },
            { id: 'whatsapp', label: 'WhatsApp' },
          ]
        ),
      };

    case 'create':
      if (ctx.role !== 'organizer' && ctx.role !== 'platform_admin') {
        return denyStaffAction(
          ctx,
          'Para crear/publicar eventos necesitas rol de organizador (o ser admin de plataforma).'
        );
      }
      return {
        reply: msg(
          'Para publicar: creas el evento, configuras boletería (mín. $15.000 en boletas de pago), eliges comisión 8%–15%, aceptas el contrato y envías a revisión. El admin global decide si sale en cartelera.',
          [
            { id: 'create_steps', label: 'Pasos para crear' },
            { id: 'create_commission', label: 'Comisión y contrato' },
            { id: 'create_review', label: '¿Qué es la revisión?' },
            { id: 'menu', label: '← Menú' },
            { id: 'whatsapp', label: 'WhatsApp' },
          ]
        ),
      };

    case 'create_steps':
      if (ctx.role !== 'organizer' && ctx.role !== 'platform_admin') {
        return denyStaffAction(ctx, 'Esa guía es para organizadores o admin de plataforma.');
      }
      return {
        reply: msg(
          'Pasos:\n' +
            '1) Inicia sesión con rol organizador.\n' +
            '2) Ve a Gestionar eventos / Panel.\n' +
            '3) Completa datos, aforo y boletería (pago ≥ $15.000).\n' +
            '4) Elige comisión 8%–15% y acepta el contrato.\n' +
            '5) Modo WhatsApp: número + mensaje base.\n' +
            '6) Guarda y «Enviar a revisión».\n' +
            '7) Tras aprobación del admin, puede ir a cartelera.',
          [
            { id: 'create_steps', label: 'Ir al panel de eventos', route: '/admin' },
            { id: 'create_commission', label: 'Comisión' },
            { id: 'create_review', label: 'Flujo de aprobación' },
            { id: 'menu', label: '← Menú' },
          ]
        ),
      };

    case 'create_commission':
      if (ctx.role !== 'organizer' && ctx.role !== 'platform_admin') {
        return denyStaffAction(ctx, 'La comisión y el contrato aplican a organizadores de eventos de pago.');
      }
      return {
        reply: msg(
          'Comisión TAVA:\n' +
            '• Eliges entre 8% y 15% sobre boletería vendida/confirmada por la página.\n' +
            '• Debes aceptar el contrato al crear el evento de pago.\n' +
            '• ~1 hora antes del evento te llega el monto a pagar al admin general.\n' +
            '• Cuando el admin confirma el dinero, se habilita el validador de ingreso.\n' +
            '• Ventas de esa última hora se ajustan después por correo.',
          [
            { id: 'settlement', label: 'Liquidación T-1h' },
            { id: 'create_steps', label: 'Cómo crear' },
            { id: 'menu', label: '← Menú' },
          ]
        ),
      };

    case 'create_review':
      return {
        reply: msg(
          'Flujo de aprobación:\n' +
            '• Organizador crea y envía a revisión.\n' +
            '• Queda pendiente (aún no en cartelera).\n' +
            '• El admin global aprueba o rechaza.\n' +
            '• Solo eventos aprobados y visibles salen en cartelera.',
          [
            { id: 'create_steps', label: 'Cómo crear' },
            { id: 'admin_panel', label: 'Ir al panel', route: '/admin' },
            { id: 'menu', label: '← Menú' },
            { id: 'whatsapp', label: 'WhatsApp' },
          ]
        ),
      };

    case 'wa_validate':
      if (ctx.role !== 'organizer' && ctx.role !== 'platform_admin') {
        return denyStaffAction(
          ctx,
          'Validar pagos WhatsApp lo hace el administrador del evento en el panel.'
        );
      }
      return {
        reply: msg(
          'Validar pagos WhatsApp:\n' +
            '1) El comprador genera el pedido en la ficha y te escribe por WhatsApp.\n' +
            '2) Cuando recibas el dinero, abre el evento en el panel.\n' +
            '3) En «Pagos WhatsApp pendientes» pulsa «Validar pago y emitir».\n' +
            '4) El sistema emite boletas y envía correo + código al comprador.',
          [
            { id: 'admin_panel', label: 'Ir al panel', route: '/admin' },
            { id: 'menu', label: '← Menú' },
          ]
        ),
      };

    case 'settlement':
      if (ctx.role === 'validator') {
        return {
          reply: msg(
            'Si el ingreso está bloqueado: falta que el organizador pague la comisión (aviso ~1h antes) y que el Administrador General confirme el dinero en el panel. Hasta entonces el validador no autoriza entrada.',
            [
              { id: 'validate_entry', label: 'Cómo validar' },
              { id: 'menu', label: '← Menú' },
              { id: 'whatsapp', label: 'WhatsApp' },
            ]
          ),
        };
      }
      if (ctx.role !== 'organizer' && ctx.role !== 'platform_admin') {
        return denyStaffAction(
          ctx,
          'La liquidación de comisión es para organizadores y el admin general de TAVA.'
        );
      }
      return {
        reply: msg(
          'Liquidación:\n' +
            '• ~1 hora antes: correo/aviso con bruto y comisión (% elegido).\n' +
            '• Organizador paga al Administrador General.\n' +
            '• Admin general confirma en el panel → se habilita el ingreso.\n' +
            '• Después del evento: ajuste por ventas extras de esa última hora.',
          [
            { id: 'admin_panel', label: 'Ir al panel', route: '/admin' },
            { id: 'create_commission', label: 'Comisión y contrato' },
            { id: 'menu', label: '← Menú' },
          ]
        ),
      };

    case 'validate_entry':
      if (ctx.role !== 'validator' && ctx.role !== 'platform_admin') {
        return denyStaffAction(ctx, 'La validación de ingreso es para el rol validador (o admin).');
      }
      return {
        reply: msg(
          'Validar ingreso:\n' +
            '1) Abre el módulo de validación.\n' +
            '2) Escanea QR o ingresa el código.\n' +
            '3) Si el evento tiene comisión y ya sonó el aviso T-1h, el ingreso puede estar bloqueado hasta que el admin general confirme el pago de la comisión.\n' +
            '4) Con el ingreso habilitado, autorizas o ves si la boleta ya fue usada.',
          [
            { id: 'validate_entry', label: 'Ir a validación', route: '/validar' },
            { id: 'settlement', label: '¿Bloqueo comisión?' },
            { id: 'menu', label: '← Menú' },
          ]
        ),
      };

    case 'sell_help':
      if (ctx.role !== 'seller' && ctx.role !== 'platform_admin') {
        return denyStaffAction(ctx, 'La venta en taquilla es para el rol vendedor (o admin).');
      }
      return {
        reply: msg(
          'En taquilla: abre el módulo de venta, elige el evento asignado, tipo de boleta y datos del comprador. Se generan boletas y, si hay correo, se envían con código de reclamo.',
          [
            { id: 'sell_help', label: 'Ir a vender', route: '/vender' },
            { id: 'menu', label: '← Menú' },
          ]
        ),
      };

    case 'admin_panel':
      if (!isStaff(ctx.role) && ctx.role !== 'platform_admin') {
        return denyStaffAction(ctx, 'El panel de gestión es para organizadores, staff o admin.');
      }
      return {
        reply: msg('Te llevo al panel de administración / eventos.', menu()),
        navigateTo: '/admin',
      };

    case 'tickets':
      return {
        reply: msg(
          'Tus boletas viven en tu perfil. Si compraste por WhatsApp, llegan cuando validen el pago. También puedes pegar un código de reclamo.',
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
        reply: msg('Te abro Mis boletas. Ahí descargas PDF y ves tus QR.', menu()),
        navigateTo: '/perfil',
      };

    case 'tickets_claim':
      return {
        reply: msg(
          'En Perfil → Reclamar código pega el código del correo o de la taquilla. Si no tienes cuenta, regístrate primero.',
          menu()
        ),
        navigateTo: '/perfil',
        fragment: 'reclamar',
      };

    case 'faq':
      return {
        reply: msg('Elige un tema. Si no está en la lista, WhatsApp con tu duda.', [
          { id: 'faq_payment', label: 'Pagos / WhatsApp' },
          { id: 'faq_email', label: 'No llegó el correo' },
          { id: 'faq_money', label: 'Comisión / liquidación' },
          { id: 'menu', label: '← Menú' },
          { id: 'whatsapp', label: 'WhatsApp' },
        ]),
      };

    case 'faq_payment':
      return {
        reply: msg(
          'Hoy muchos eventos cobran por WhatsApp: generas el pedido en la web, pagas como te indiquen y el organizador valida en TAVA. Entonces se emite la boleta. Si el evento usa pago en sistema (Wompi), el checkout es en la ficha.',
          [
            { id: 'buy_how', label: 'Cómo comprar' },
            { id: 'faq', label: '← FAQ' },
            { id: 'whatsapp', label: 'WhatsApp' },
          ]
        ),
      };

    case 'faq_email':
      return {
        reply: msg(
          'Revisa spam. Si fue compra WhatsApp, el correo sale cuando validan el pago. También puedes ver/descargar en Mis boletas o usar el código de reclamo.',
          [
            { id: 'tickets_mine', label: 'Mis boletas', route: '/perfil' },
            { id: 'faq', label: '← FAQ' },
            { id: 'whatsapp', label: 'WhatsApp' },
          ]
        ),
      };

    case 'faq_money':
      if (ctx.role === 'organizer' || ctx.role === 'platform_admin') {
        return resolveTavoAction('settlement', events, ctx);
      }
      return {
        reply: msg(
          'La comisión (8%–15%) la acuerda el organizador con TAVA al crear el evento. Se liquida cerca del inicio de la función. Si eres comprador, solo pagas el valor de tu boleta en la ficha / WhatsApp del evento.',
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
          menu()
        ),
        openWhatsapp: buildWhatsappUrl('Necesito ayuda con la plataforma TAVA.'),
      };

    case 'bye':
      return {
        reply: msg(
          'Gracias por conversar conmigo. Cuando quieras, aquí estaré. ¡Que disfrutes la función! 🎭',
          menu()
        ),
      };

    default:
      return {
        reply: msg(isStaff(ctx.role) ? TAVO_SCOPE_STAFF : TAVO_SCOPE_CLIENT, menu()),
      };
  }
}

/** Interpreta texto libre del usuario (MVP por palabras clave + cartelera). */
export function resolveTavoFreeText(
  raw: string,
  events: TavoEventBrief[] = [],
  ctx: TavoUserContext = { role: 'guest', loggedIn: false }
): TavoResolveResult {
  const t = raw.trim().toLowerCase();
  const menu = () => menuButtons(ctx);

  if (!t) {
    return { reply: msg('Cuéntame tu duda o elige un botón.', menu()) };
  }

  if (isCapabilityQuestion(t)) {
    return capabilityReply(ctx);
  }

  if (/hola|buenas|hey|saludos/.test(t)) {
    return resolveTavoAction('menu', events, ctx);
  }
  if (/gracias|chao|adi[oó]s|hasta luego/.test(t)) {
    return resolveTavoAction('bye', events, ctx);
  }
  if (/whatsapp|humano|asesor|hablar con/.test(t)) {
    return {
      reply: msg('Claro. Te paso a WhatsApp con tu mensaje.', menu()),
      openWhatsapp: buildWhatsappUrl(raw),
    };
  }

  const matched = findMatchingEvents(raw, events);
  const wantsPrice = /precio|cu[aá]nto|vale|costo|valor/.test(t);
  const wantsEvents =
    /evento|obra|funci[oó]n|cartelera|qu[eé] hay|qu[eé] presentan|programaci[oó]n/.test(t);

  if (matched.length === 1) {
    const ev = matched[0];
    const eventRoute = `/eventos/${ev.id}`;
    if (wantsPrice) {
      return {
        reply: msg('Busco la boletería de esa función…', [
          { id: 'buy_cartelera', label: 'Ver ficha', route: eventRoute },
          { id: 'menu', label: '← Menú' },
        ]),
        fetchEventId: ev.id,
      };
    }
    return {
      reply: msg(formatEventInfo(ev, !!ev.ticket_types?.length), [
        { id: 'buy_cartelera', label: 'Ver ficha', route: eventRoute },
        { id: 'buy_how', label: 'Cómo comprar' },
        { id: 'menu', label: '← Menú' },
        { id: 'whatsapp', label: 'WhatsApp' },
      ]),
    };
  }

  if (matched.length > 1) {
    const block = matched.map((ev) => formatEventInfo(ev)).join('\n\n———\n\n');
    return {
      reply: msg(`Encontré varias coincidencias:\n\n${block}`, [
        { id: 'buy_cartelera', label: 'Abrir cartelera', route: '/eventos' },
        { id: 'events_info', label: 'Listar cartelera' },
        { id: 'menu', label: '← Menú' },
      ]),
    };
  }

  if (wantsEvents || (wantsPrice && !matched.length)) {
    return {
      reply: msg(
        wantsPrice
          ? `${listCarteleraSummary(events)}\n\nEscribe el nombre de la obra y te doy fecha, lugar y precios.`
          : `${listCarteleraSummary(events)}\n\nEscribe el nombre de una obra para ver el detalle.`,
        [
          { id: 'buy_cartelera', label: 'Abrir cartelera', route: '/eventos' },
          { id: 'buy_how', label: 'Cómo comprar' },
          { id: 'menu', label: '← Menú' },
          { id: 'whatsapp', label: 'WhatsApp' },
        ]
      ),
    };
  }

  if (/comisi[oó]n|contrato|liquidaci[oó]n|10\s*%|8\s*%|15\s*%/.test(t)) {
    if (ctx.role === 'organizer' || ctx.role === 'platform_admin') {
      return resolveTavoAction(
        /liquidaci[oó]n|1\s*h|una hora/.test(t) ? 'settlement' : 'create_commission',
        events,
        ctx
      );
    }
    return resolveTavoAction('faq_money', events, ctx);
  }

  if (/validar pago|whatsapp pendiente|emitir boleta/.test(t)) {
    return resolveTavoAction('wa_validate', events, ctx);
  }

  if (/validar|ingreso|escane|qr|validador/.test(t) && (ctx.role === 'validator' || ctx.role === 'platform_admin')) {
    return resolveTavoAction('validate_entry', events, ctx);
  }

  if (/taquilla|vender/.test(t) && (ctx.role === 'seller' || ctx.role === 'platform_admin')) {
    return resolveTavoAction('sell_help', events, ctx);
  }

  if (/comprar|boleta|ticket/.test(t)) {
    return resolveTavoAction('buy', events, ctx);
  }
  if (/crear|publicar|organizador|revisi[oó]n|aprobar/.test(t) && !/boleta/.test(t)) {
    if (/aprobar|revisi[oó]n|pendiente/.test(t)) {
      return resolveTavoAction('create_review', events, ctx);
    }
    return resolveTavoAction('create', events, ctx);
  }
  if (/reclamar|c[oó]digo|mis boletas|pdf/.test(t)) {
    return resolveTavoAction('tickets', events, ctx);
  }
  if (/pago|wompi|correo|email|dinero|venta/.test(t)) {
    return resolveTavoAction('faq', events, ctx);
  }

  return {
    reply: msg(
      `${isStaff(ctx.role) ? TAVO_SCOPE_STAFF : TAVO_SCOPE_CLIENT}\n\nTambién puedo reenviar tu duda a WhatsApp.`,
      [
        { id: 'menu', label: 'Ver opciones' },
        { id: 'events_info', label: 'Ver eventos' },
        { id: 'whatsapp', label: 'Enviar esta duda por WhatsApp' },
      ]
    ),
  };
}

export function isWhatsappHandoffIntent(text: string): boolean {
  return /whatsapp|enviar esta duda/i.test(text);
}

/** Deriva el contexto Tavo desde el usuario de AuthService. */
export function tavoContextFromUser(user: {
  role?: string;
  is_platform_admin?: boolean;
} | null): TavoUserContext {
  if (!user) return { role: 'guest', loggedIn: false };
  if (user.is_platform_admin) return { role: 'platform_admin', loggedIn: true };
  const raw = (user.role || 'general').toLowerCase();
  if (raw === 'admin') return { role: 'platform_admin', loggedIn: true };
  if (raw === 'organizer') return { role: 'organizer', loggedIn: true };
  if (raw === 'validator') return { role: 'validator', loggedIn: true };
  if (raw === 'seller') return { role: 'seller', loggedIn: true };
  return { role: 'general', loggedIn: true };
}
