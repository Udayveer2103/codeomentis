const API_URL = import.meta.env.VITE_API_URL as string;

// Exported for streaming or other low-level HTTP requests that cannot
// use the JSON-based request<T>() helper below (e.g. SSE via fetch() +
// ReadableStream, file uploads/downloads) — request<T>() always calls
// res.json(), which assumes a single parseable JSON response body.
export const API_BASE_URL = API_URL;

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
  ...options,
  headers: {
    "Content-Type": "application/json",
    ...(options.headers ?? {}),
  },
});

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail ?? `HTTP ${res.status}`);
  }

  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string, headers?: HeadersInit) =>
    request<T>(path, { method: "GET", headers }),

  post: <T>(path: string, body: unknown, headers?: HeadersInit) =>
    request<T>(path, {
      method: "POST",
      body: JSON.stringify(body),
      headers,
    }),
};