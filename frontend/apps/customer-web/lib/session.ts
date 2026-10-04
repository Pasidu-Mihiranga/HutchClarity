/**
 * The customer's session token, and what happens when the API stops
 * accepting it.
 *
 * A token can be refused because it expired, because the customer signed out
 * elsewhere, or because the server's signing key changed. Before this, every
 * call after that point failed with a 401 the customer never saw explained:
 * the chat simply stopped answering. A refused token is now cleared and the
 * customer is sent to sign in again, then back to the page they were on.
 */

export const TOKEN_KEY = "clarity_token";

export function readToken(): string | null {
  try {
    return window.sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

/** Only same-origin paths are accepted as a return address, never `//host`. */
export function safeNext(raw: string | null): string {
  return raw && raw.startsWith("/") && !raw.startsWith("//") ? raw : "/";
}

/** Drop the refused token and go to sign-in, remembering where we were. */
export function expireSession(): void {
  try {
    window.sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: there is no token to clear */
  }
  const here = window.location.pathname + window.location.search;
  if (window.location.pathname.startsWith("/login")) return;
  window.location.assign(`/login?next=${encodeURIComponent(here)}`);
}
