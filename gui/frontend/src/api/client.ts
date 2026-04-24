/**
 * Minimal fetch wrapper. Accepts a path under /api and returns parsed JSON.
 * Throws on non-2xx so react-query treats it as an error.
 */
export async function api<T = unknown>(
  path: string,
  init?: RequestInit & { json?: unknown },
): Promise<T> {
  const headers = new Headers(init?.headers);
  let body = init?.body;
  if (init?.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  const res = await fetch(path, { ...init, headers, body });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text || path}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
