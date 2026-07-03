const MESSAGES: Record<string, string[]> = {
  general: [
    'Bajando el telón un momento…',
    'Los actores respiran hondo…',
    'Afinando las luces del escenario…',
    'El público guarda silencio…',
  ],
  login: [
    'Revisando tu entrada en la taquilla…',
    'El acomodador busca tu asiento…',
    'Las cortinas se abren en 3, 2…',
    'Validando credenciales tras bambalinas…',
  ],
  register: [
    'Escribiendo tu nombre en el programa de mano…',
    'Reservando butaca con tu nombre…',
    'Enviando la invitación por paloma mensajera…',
    'El tramoyista prepara tu ficha de artista…',
  ],
  verify: [
    'El director revisa el enlace…',
    'Confirmando que no eres un extra…',
    'Aplauso en espera…',
    'Verificando el sello del teatro…',
  ],
  resend: [
    'El correo vuela hacia tu bandeja…',
    'La mensajera del teatro sale en escena…',
    'Reenviando la invitación con aplausos…',
  ],
  purchase: [
    'Preparando tus boletas digitales…',
    'Validando disponibilidad en taquilla…',
    'La taquilla acomoda tu orden…',
    'Reservando tu lugar para la función…',
    'Un momento, estamos dejando todo listo…',
  ],
  validation: [
    'Escaneando tu QR como crítico de estreno…',
    'La puerta del teatro revisa tu pase…',
    'Un segundo, que pasa el validador…',
  ],
  admin: [
    'El director de escena organiza el caos…',
    'Actualizando el libreto…',
    'Los reflectores apuntan a la base de datos…',
  ],
  upload: [
    'Subiendo el archivo al camerino…',
    'El proyector calienta motores…',
    'Guardando escena en el archivador…',
  ],
  forgot: [
    'El tramoyista busca tu contraseña perdida…',
    'Enviando paloma con enlace de rescate…',
    'La taquilla reimprime tu pase de memoria…',
  ],
  delete: [
    'Retirando del reparto con drama…',
    'Último curtain call para este registro…',
    'Borrando con efecto de niebla…',
  ],
  loader: [
    'Trayendo información del servidor al teatro…',
    'El tramoyista corre al almacén de datos…',
    'Construyendo el escenario digital ladrillo a ladrillo…',
    'Despertando al servidor en la bodega (cuesta, pero llega)…',
    'Los actores esperan mientras llega el libreto…',
    'El director grita: «¡Que entre la cartelera!»…',
    'Afinando las luces mientras cargan los eventos…',
    'El prompter busca el USB con la programación…',
  ],
};

const POPUP_PHRASES = [
  '¡Bravo! El público aplaude tu paciencia…',
  'Un tramoyista tropezó, pero el show continúa.',
  'Las rosas vuelan hacia el escenario…',
  'El director susurra: “casi, casi…”',
  'Intervalo express: respira como estrella.',
  'La orquesta afina un acorde cómico.',
  'Curtain call en camino…',
  'El prompter hace malabares con los datos.',
  '¡Otro aplauso del público imaginario!',
  'Los reflectores buscan tu butaca en la nube.',
];

export function randomTheatricalMessage(context = 'general'): string {
  const list = MESSAGES[context] ?? MESSAGES['general'];
  return list[Math.floor(Math.random() * list.length)];
}

export function randomPopupPhrase(): string {
  return POPUP_PHRASES[Math.floor(Math.random() * POPUP_PHRASES.length)];
}
