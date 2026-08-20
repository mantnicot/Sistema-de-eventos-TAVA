export function matchesSearch(query: string, ...fields: Array<string | number | boolean | null | undefined>): boolean {
  const raw = query.trim().toLowerCase();
  if (!raw) return true;
  const haystack = fields
    .map((field) => (field == null ? '' : String(field).toLowerCase()))
    .join(' ');
  return raw.split(/\s+/).every((token) => haystack.includes(token));
}
