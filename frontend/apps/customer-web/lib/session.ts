/**
 * The customer's session, and what happens when the API stops accepting it.
 *
 * **The session is a cookie now, not a token this code can read** (B4). It was
 * kept in `sessionStorage`, where any script on the page can read it, and it
 * is the credential that opens a dispute and confirms a refund. The API sets
 * it `HttpOnly` on sign-in, so every request carries it automatically and
 * nothing here can hand it to anyone.
 *
 * What this file still does is the half a cookie cannot: send credentials on
 * cross-origin requests (the API is a different origin from the app), echo the
 * CSRF token, and notice when a session has been refused.
 *
 * A token can be refused because it expired, because the customer signed out
 * elsewhere, or because the server's signing key rotated past its overlap
 * window. Before this was handled, every call after that point failed with a
 * 401 the customer never saw explained: the chat simply stopped answering.
 */

/** The CSRF cookie the API sets beside the session. Readable on purpose. */
export const CSRF_COOKIE = "clarity_csrf";
export const CSRF_HEADER = "X-CSRF-Token";

/** Read a cookie this page is allowed to see. The session is not one of them. */
export function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const found = document.cookie
    .split("; ")
    .find((entry) => entry.startsWith(`${name}=`));
  return found ? decodeURIComponent(found.slice(name.length + 1)) : null;
}

/**
 * Everything a request needs to be recognised: credentials, and the CSRF
 * token echoed back in a header.
 *
 * `credentials: "include"` rather than the default, because the API is a
 * different origin from the app and the browser would otherwise drop the
 * cookie. The API pins CORS to this origin, which is what makes that safe.
 */
export function withSession(init: RequestInit = {}): RequestInit {
  const headers = new Headers(init.headers);
  const csrf = readCookie(CSRF_COOKIE);
  if (csrf) headers.set(CSRF_HEADER, csrf);
  return { ...init, headers, credentials: "include" };
}

/** Only same-origin paths are accepted as a return address, never `//host`. */
export function safeNext(raw: string | null): string {
  return raw && raw.startsWith("/") && !raw.startsWith("//") ? raw : "/";
}

/**
 * The session was refused. Send the customer to sign in, remembering where
 * they were.
 *
 * Nothing is cleared here: the session cookie is `HttpOnly`, so only the API
 * can remove it, and it does so on sign-out. A page that tried to clear it
 * would be writing a cookie it cannot read, which is how you end up with two.
 */
export function expireSession(): void {
  const here = window.location.pathname + window.location.search;
  if (window.location.pathname.startsWith("/login")) return;
  window.location.assign(`/login?next=${encodeURIComponent(here)}`);
}
