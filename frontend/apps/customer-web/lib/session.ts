/**
 * The customer's session: access token, refresh token, and every call to the
 * API that needs them.
 *
 * Access tokens live ten minutes (iam.tokens). The API also issues a refresh
 * token at sign-in; before this file used it, every customer was sent back to
 * sign-in ten minutes after signing in. Now a 401 triggers one refresh and a
 * retry, and only a refused refresh ends the session, which then goes to
 * sign-in and back to the page the customer was on.
 *
 * Both tokens are kept in `sessionStorage`, so they die with the tab.
 */

export const TOKEN_KEY = "clarity_token";
const REFRESH_KEY = "clarity_refresh";

export const BASE =
  typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000")
    : "http://localhost:8000";

function read(key: string): string | null {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

export function readToken(): string | null {
  return read(TOKEN_KEY);
}

/** Keep a freshly issued session. */
export function storeSession(token: string, refreshToken?: string | null): void {
  try {
    window.sessionStorage.setItem(TOKEN_KEY, token);
    if (refreshToken) window.sessionStorage.setItem(REFRESH_KEY, refreshToken);
  } catch {
    /* storage unavailable: the session lasts until the token expires */
  }
}

export function clearSession(): void {
  try {
    window.sessionStorage.removeItem(TOKEN_KEY);
    window.sessionStorage.removeItem(REFRESH_KEY);
  } catch {
    /* nothing to clear */
  }
}

/** Only same-origin paths are accepted as a return address, never `//host`. */
export function safeNext(raw: string | null): string {
  return raw && raw.startsWith("/") && !raw.startsWith("//") ? raw : "/";
}

/** Drop the session and go to sign-in, remembering where we were. */
export function expireSession(): void {
  clearSession();
  const here = window.location.pathname + window.location.search;
  if (window.location.pathname.startsWith("/login")) return;
  window.location.assign(`/login?next=${encodeURIComponent(here)}`);
}

/** Thrown after the page has been sent to sign-in; callers just stop. */
export class SessionEnded extends Error {
  constructor() {
    super("session ended");
    this.name = "SessionEnded";
  }
}

// One refresh at a time. The server rotates refresh tokens and refuses a
// reused one, so two requests refreshing in parallel would end the session.
let refreshing: Promise<string | null> | null = null;

async function refreshSession(): Promise<string | null> {
  const refreshToken = read(REFRESH_KEY);
  if (!refreshToken) return null;
  try {
    const res = await fetch(`${BASE}/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return null;
    const body = (await res.json()) as { token: string; refresh_token?: string | null };
    storeSession(body.token, body.refresh_token);
    return body.token;
  } catch {
    return null;
  }
}

/**
 * `fetch` with the session attached. A 401 refreshes once and retries; if the
 * refresh is refused too, the session ends and the customer goes to sign-in.
 * The caller never sees a 401: it gets a response or a `SessionEnded`.
 */
export async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const send = (token: string) =>
    fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init.headers, Authorization: `Bearer ${token}` },
    });

  const token = readToken();
  if (!token) {
    expireSession();
    throw new SessionEnded();
  }
  const first = await send(token);
  if (first.status !== 401) return first;

  refreshing ??= refreshSession().finally(() => {
    refreshing = null;
  });
  const renewed = await refreshing;
  const second = renewed ? await send(renewed) : null;
  if (!second || second.status === 401) {
    expireSession();
    throw new SessionEnded();
  }
  return second;
}
