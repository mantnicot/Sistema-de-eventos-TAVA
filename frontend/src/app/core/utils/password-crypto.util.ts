/** Cifra la contraseña con la clave pública del API (RSA-OAEP). El inspector verá solo Base64. */
export async function encryptPasswordForTransport(
  publicKeyPem: string,
  password: string
): Promise<string> {
  const pemBody = publicKeyPem
    .replace(/-----BEGIN PUBLIC KEY-----/g, '')
    .replace(/-----END PUBLIC KEY-----/g, '')
    .replace(/\s/g, '');
  const binary = Uint8Array.from(atob(pemBody), (c) => c.charCodeAt(0));
  const key = await crypto.subtle.importKey(
    'spki',
    binary.buffer,
    { name: 'RSA-OAEP', hash: 'SHA-256' },
    false,
    ['encrypt']
  );
  const encrypted = await crypto.subtle.encrypt(
    { name: 'RSA-OAEP' },
    key,
    new TextEncoder().encode(password)
  );
  const bytes = new Uint8Array(encrypted);
  let binaryStr = '';
  for (let i = 0; i < bytes.length; i++) {
    binaryStr += String.fromCharCode(bytes[i]);
  }
  return btoa(binaryStr);
}
