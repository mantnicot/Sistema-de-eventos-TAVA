export interface MediaUploadSpec {
  title: string;
  lines: string[];
}

export const IMAGE_EVENT_SPEC: MediaUploadSpec = {
  title: 'Imagen del evento (cartel / lámina)',
  lines: [
    'Resolución recomendada: 1200 × 1600 px (vertical, tipo póster) o 1200 × 675 px (horizontal 16:9)',
    'Mínimo: 800 px de ancho · Ideal: 1200–1920 px',
    'Formato: JPG, PNG o WebP · Calidad 80–85% (buen equilibrio peso/nitidez)',
    'Peso máximo: 8 MB',
    'Usa buena luz, texto legible y sin bordes cortados — esta imagen aparece en cartelera, boletas y colección',
  ],
};

export const VIDEO_TRAILER_SPEC: MediaUploadSpec = {
  title: 'Video trailer',
  lines: [
    'Resolución recomendada: 1920 × 1080 px (Full HD, 16:9)',
    'Formato: MP4 (H.264) o WebM · Máximo 80 MB',
    'Duración ideal: 30 segundos – 2 minutos',
    'Recomendado: enlace de YouTube/Vimeo (no se pierde al redeploy) en lugar de subir archivo',
    'Si subes archivo, usa Cloudinary configurado en Render para que persista',
  ],
};

export const VIDEO_HERO_SPEC: MediaUploadSpec = {
  title: 'Video de fondo (inicio)',
  lines: [
    'Resolución: 1920 × 1080 px (16:9) · MP4 H.264',
    'Duración: 10–30 seg en loop, sin audio fuerte',
    'Peso máximo: 80 MB · Evita archivos muy pesados para carga rápida',
  ],
};

export const GALLERY_IMAGE_SPEC: MediaUploadSpec = {
  title: 'Foto de galería',
  lines: [
    'Resolución: 1200 × 900 px o superior',
    'JPG/WebP, calidad 80%, máximo 8 MB',
  ],
};

export const GALLERY_VIDEO_SPEC: MediaUploadSpec = {
  title: 'Video de galería',
  lines: [
    '1920 × 1080 px · MP4 · Máx. 80 MB · Clips cortos (15–60 seg)',
  ],
};
