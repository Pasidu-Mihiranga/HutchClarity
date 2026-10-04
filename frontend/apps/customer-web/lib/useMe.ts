"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ClarityApiError, ClarityClient, type CustomerApp } from "@clarity/sdk";
import { expireSession } from "./session";

/**
 * The signed-in customer's account, for every screen that renders it (E4).
 *
 * **Why one hook and one payload.** `GET /v1/me/app` is documented in the SDK
 * as "the one customer read: every screen renders this payload", and every
 * `/v1/me/*` write returns the refreshed payload. So a write does not need a
 * reload and the screens do not need to agree on what changed: the server
 * sends the new truth back and this replaces its state with it. That is also
 * what stops the balance on Home disagreeing with the balance on Usage.
 *
 * **Why the pages had to change at all.** Home was a `const DEMO` object with
 * a name, a number and a balance written into the source. `/cases` called a
 * method the client does not have and fell back to two invented rows. The case
 * page fabricated a VAS charge when the request failed. All three showed a
 * customer figures no system had produced, which is the opposite of what a
 * product built on evidence is for (I2, I16).
 *
 * **A failure is never filled in.** There is no fallback object here. A load
 * that fails leaves `app` null and sets `error`, and the pages render an error
 * state. A 401 is different from an error: the session has been refused, so
 * `expireSession()` sends the customer to sign in with a return address rather
 * than showing them a page that cannot work.
 */

/** One client for the app. The session is an HttpOnly cookie the SDK sends. */
const client = new ClarityClient();

export type MeState = {
  app: CustomerApp | null;
  /** True only on the first load, so a refresh does not blank the screen. */
  loading: boolean;
  error: string | null;
  /** Re-read the payload. */
  refresh: () => void;
  /**
   * Run a write and adopt the payload it returns.
   *
   * Returns true when it succeeded, so a caller can close its dialog only on
   * success and leave it open with the message when the API refused.
   */
  act: (run: (api: ClarityClient) => Promise<CustomerApp>) => Promise<boolean>;
  /** Set while a write is in flight. */
  busy: boolean;
};

export function useMe(): MeState {
  const [app, setApp] = useState<CustomerApp | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generation, setGeneration] = useState(0);
  const live = useRef(true);

  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const payload = await client.myApp();
        if (!cancelled) {
          setApp(payload);
          setError(null);
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ClarityApiError && (err.status === 401 || err.status === 403)) {
          expireSession();
          return;
        }
        setError(err instanceof Error ? err.message : "Your account could not be loaded.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [generation]);

  const refresh = useCallback(() => setGeneration((n) => n + 1), []);

  const act = useCallback(async (run: (api: ClarityClient) => Promise<CustomerApp>) => {
    setBusy(true);
    setError(null);
    try {
      const payload = await run(client);
      if (live.current) setApp(payload);
      return true;
    } catch (err) {
      if (err instanceof ClarityApiError && (err.status === 401 || err.status === 403)) {
        expireSession();
        return false;
      }
      // The API's own refusal is the message. "choose a listed reload amount"
      // tells the customer what to do; "something went wrong" does not.
      if (live.current) {
        setError(err instanceof Error ? err.message : "That did not go through.");
      }
      return false;
    } finally {
      if (live.current) setBusy(false);
    }
  }, []);

  return { app, loading, error, refresh, act, busy };
}

export { client as meClient };
