"use client";

import { useState } from "react";
import Link from "next/link";
import { Alert, Textarea } from "@clarity/ui";
import { ClarityApiError, type OfferCheckView } from "@clarity/sdk";
import { expireSession } from "@/lib/session";
import { meClient } from "@/lib/useMe";

/**
 * "Is this message real?" (OFFER01)
 *
 * A customer gets an SMS saying HUTCH has given them 10GB free and wants to
 * know whether to believe it. They paste it here and the answer comes from
 * what HUTCH actually sent that number.
 *
 * **Why this is a screen the customer opens, and not something the chat
 * guesses at.** The alternative was to watch what somebody types and decide
 * when it looks like a forwarded offer. That is the client inferring intent,
 * which is the pattern FE01 called out as an I1 violation elsewhere in this
 * app, and it would fail in the direction that matters: a scam the heuristic
 * did not recognise gets no check at all. Here the customer says what they
 * want, so nothing is inferred and nothing is missed.
 *
 * **The verdict is never "this is a scam".** Three answers come back, and each
 * says what was checked: the offer is on record, nothing on record matches it,
 * or it partly matches and a person should look. Saying "scam" would be an
 * inference past the evidence - the record could be missing, the campaign
 * could have come from a partner - and the thing that actually protects
 * somebody is knowing HUTCH has no record of it and that the message is asking
 * for their PIN. Both of those are on the screen.
 */

/** What each warning sign means, in words a customer can act on. */
const SIGNALS: Record<string, { title: string; body: string }> = {
  LINK: {
    title: "It contains a link",
    body: "Hutch offers are applied to your account and shown in the app. You never need to follow a link to claim one.",
  },
  NON_HUTCH_LINK: {
    title: "The link is not a Hutch address",
    body: "It points somewhere that is not hutch.lk. A lookalike address is the most common way a fake offer is made to look real.",
  },
  ASKS_FOR_CODE: {
    title: "It asks for a code, PIN or password",
    body: "Hutch will never ask you for an OTP, a PIN or a password. Anyone who does is trying to get into your account.",
  },
  ASKS_TO_CALL: {
    title: "It asks you to call or message a number",
    body: "A real offer needs no phone call. Use the number on the back of your SIM pack or in the app if you want to check with Hutch.",
  },
  ASKS_FOR_PAYMENT: {
    title: "It asks for money or card details",
    body: "A Hutch offer is added to your account. You are never asked to pay a fee or share card details to release one.",
  },
  URGENCY: {
    title: "It pushes you to act immediately",
    body: "Being rushed is how someone is stopped from checking. A real offer is still there in the app in ten minutes.",
  },
};

type Verdict = "ON_RECORD" | "NOT_ON_RECORD" | "NEEDS_A_PERSON";

function headline(result: OfferCheckView): { tone: "success" | "danger" | "warning"; title: string; body: string } {
  const verdict = result.verdict as Verdict;
  const matched = result.matched;

  if (verdict === "ON_RECORD" && matched?.still_valid) {
    return {
      tone: "success",
      title: "This offer is on your number",
      body: "Hutch sent this to you and it is still running. You can see it in the app under Packages.",
    };
  }
  if (verdict === "ON_RECORD") {
    return {
      tone: "warning",
      title: "This was a real offer, and it has ended",
      body: "Hutch did send you this, so the message is not a fake. The offer itself is no longer running, so nothing will be added to your account now.",
    };
  }
  if (verdict === "NEEDS_A_PERSON") {
    return {
      tone: "warning",
      title: "This is close to a real offer, but not the same",
      body: "Part of it matches something Hutch sent you and part of it does not, which is what an edited message looks like. We have not decided it either way. Ask Clarity and a person will look at it.",
    };
  }
  if (result.offers_on_record === 0) {
    return {
      tone: "danger",
      title: "Your number has no offers on record",
      body: "There is nothing on your number for this message to match, so Hutch has no record of sending it to you.",
    };
  }
  return {
    tone: "danger",
    title: "Hutch has no record of this offer for your number",
    body: "We checked what Hutch sent to your number and nothing matches this message. A real Hutch offer always shows in the app under Packages. If it is not there, do not act on the message.",
  };
}

export default function CheckMessagePage() {
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<OfferCheckView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function check() {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await meClient.verifyOfferMessage(message));
    } catch (err) {
      if (err instanceof ClarityApiError && (err.status === 401 || err.status === 403)) {
        expireSession();
        return;
      }
      setError(err instanceof Error ? err.message : "We could not check that message.");
    } finally {
      setBusy(false);
    }
  }

  const verdict = result ? headline(result) : null;

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
      <h1
        style={{
          fontSize: 22,
          fontWeight: 800,
          letterSpacing: "-.02em",
          margin: "0 0 6px",
          color: "var(--ink)",
        }}
      >
        Is this message real?
      </h1>
      <p style={{ fontSize: 14, color: "var(--muted)", margin: "0 0 18px" }}>
        Paste a message you were sent. We check it against what Hutch actually
        sent to your number.
      </p>

      <section aria-labelledby="check-paste" className="h-card" style={{ marginBottom: 14 }}>
        <h2 id="check-paste" className="sr-only">
          The message you received
        </h2>
        <label
          htmlFor="offer-message"
          style={{ display: "block", fontSize: 13, fontWeight: 650, marginBottom: 6 }}
        >
          The message
        </label>
        <Textarea
          id="offer-message"
          rows={6}
          placeholder="Paste the whole message here, including any link or code it contains."
          value={message}
          onChange={(event) => setMessage(event.target.value)}
        />
        <p style={{ fontSize: 12, color: "var(--muted)", margin: "8px 0 0" }}>
          We do not keep the message. It is used to find which offer to compare
          against and then discarded.
        </p>
        <button
          type="button"
          className="h-btn h-btn-primary"
          style={{ marginTop: 12, width: "100%" }}
          disabled={busy || !message.trim()}
          onClick={() => void check()}
        >
          {busy ? "Checking…" : "Check this message"}
        </button>
      </section>

      {error ? (
        <div style={{ marginBottom: 14 }}>
          <Alert tone="danger">{error}</Alert>
        </div>
      ) : null}

      {result && verdict ? (
        <section aria-labelledby="check-result" aria-live="polite">
          <h2 id="check-result" className="sr-only">
            What we found
          </h2>
          <div style={{ marginBottom: 14 }}>
            <Alert tone={verdict.tone} title={verdict.title}>
              {verdict.body}
            </Alert>
          </div>

          {result.matched ? (
            <div className="h-card" style={{ marginBottom: 14 }}>
              <p
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: ".06em",
                  color: "var(--muted)",
                  margin: "0 0 6px",
                }}
              >
                What Hutch sent you
              </p>
              <p style={{ margin: 0, fontWeight: 700, fontSize: 16 }}>
                {result.matched.title}
              </p>
              <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--muted)" }}>
                {result.matched.still_valid ? "Running" : "Ended"} ·{" "}
                {new Date(result.matched.valid_from).toLocaleDateString()}
                {result.matched.valid_to
                  ? ` to ${new Date(result.matched.valid_to).toLocaleDateString()}`
                  : ""}
                {result.matched.offer_code ? ` · code ${result.matched.offer_code}` : ""}
              </p>
            </div>
          ) : null}

          {result.signals.length > 0 ? (
            <section aria-labelledby="check-signals" style={{ marginBottom: 14 }}>
              <h3
                id="check-signals"
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: ".06em",
                  color: "var(--muted)",
                  margin: "0 0 8px",
                }}
              >
                Things to look at in the message
              </h3>
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 8 }}>
                {result.signals.map((signal) => {
                  const known = SIGNALS[signal.code];
                  if (!known) return null;
                  return (
                    <li key={signal.code} className="h-card">
                      <p style={{ margin: 0, fontWeight: 650, fontSize: 14 }}>{known.title}</p>
                      <p style={{ margin: "3px 0 0", fontSize: 13, color: "var(--muted)" }}>
                        {known.body}
                      </p>
                    </li>
                  );
                })}
              </ul>
            </section>
          ) : null}

          <p style={{ fontSize: 13, color: "var(--muted)", margin: "0 0 14px" }}>
            We checked {result.offers_on_record}{" "}
            {result.offers_on_record === 1 ? "offer" : "offers"} on record for your
            number.
          </p>

          <Link
            href="/clarity"
            style={{
              display: "block",
              textAlign: "center",
              fontSize: 14,
              fontWeight: 650,
              color: "var(--orange-ink)",
              padding: "10px 0",
              textDecoration: "none",
            }}
          >
            Ask Clarity about this →
          </Link>
        </section>
      ) : null}

      {/* I16: the offer records behind this answer are simulated. */}
      <p
        style={{
          border: "1px solid rgb(var(--c-primary) / 0.3)",
          borderRadius: "var(--radius-card-sm)",
          background: "var(--orange-soft)",
          padding: "10px 14px",
          fontSize: 13,
          color: "var(--orange-ink)",
          margin: "14px 0 0",
        }}
      >
        <strong>SIMULATED</strong> - the offer records this is checked against
        are simulated, not a live Hutch campaign system.
      </p>
    </main>
  );
}
