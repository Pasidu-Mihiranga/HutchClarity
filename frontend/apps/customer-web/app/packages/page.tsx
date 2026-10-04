"use client";

import { useState } from "react";
import { Alert, Dialog, EmptyState, ErrorState, Skeleton } from "@clarity/ui";
import type { CatalogueOffering, CustomerSubscription } from "@clarity/sdk";
import { useMe } from "@/lib/useMe";

/**
 * Packages (E4).
 *
 * Home's "Packages" quick action pointed at `"#"`. The payload and the routes
 * it needed already existed and nothing read them: `/v1/me/app` carries the
 * catalogue and the active subscriptions, and
 * `POST /v1/me/packages/{id}/purchase` and
 * `POST /v1/me/subscriptions/{id}/cancel` do the two things a customer wants
 * to do here.
 *
 * **Both writes confirm first**, because both move money: a purchase debits
 * the balance and a cancellation ends something the customer may be relying
 * on. The dialog states the price from the offering, never a price this page
 * worked out.
 *
 * **Why the fair-use terms are on the card.** `after_cap_speed` is the thing
 * that generates the complaint Clarity then has to explain ("my data stopped
 * working"), so it is shown before the purchase rather than discovered after
 * it. The disclosure is the offering's own field.
 */

type Confirming =
  | { kind: "buy"; offering: CatalogueOffering }
  | { kind: "cancel"; subscription: CustomerSubscription }
  | null;

export default function PackagesPage() {
  const { app, loading, error, refresh, act, busy } = useMe();
  const [confirming, setConfirming] = useState<Confirming>(null);

  async function run() {
    if (!confirming) return;
    const ok =
      confirming.kind === "buy"
        ? await act((api) => api.purchasePackage(confirming.offering.offering_id))
        : await act((api) => api.cancelSubscription(confirming.subscription.id));
    if (ok) setConfirming(null);
  }

  if (loading) {
    return (
      <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
        <p role="status" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>
          Loading packages
        </p>
        <div style={{ display: "grid", gap: 12 }}>
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} style={{ height: 110, borderRadius: "var(--radius)" }} />
          ))}
        </div>
      </main>
    );
  }

  if (!app) {
    return (
      <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
        <ErrorState
          title="We could not load the packages"
          message={error ?? "Please try again in a moment."}
          onRetry={refresh}
        />
      </main>
    );
  }

  const active = app.subscriptions.filter((sub) => sub.active);

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
      <h1 style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-.02em", margin: "0 0 4px" }}>
        Packages
      </h1>
      <p style={{ fontSize: 13, color: "var(--muted)", margin: "0 0 18px" }}>
        Your balance is LKR {app.balance_lkr}. Buying a pack takes the price from it.
      </p>

      {error ? (
        <div style={{ marginBottom: 14 }}>
          <Alert tone="danger">{error}</Alert>
        </div>
      ) : null}

      <section aria-labelledby="packages-active" style={{ marginBottom: 24 }}>
        <h2
          id="packages-active"
          style={{
            fontSize: 11,
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: ".08em",
            color: "var(--muted)",
            margin: "0 0 10px",
          }}
        >
          Active subscriptions
        </h2>
        {active.length === 0 ? (
          <p className="h-card" style={{ fontSize: 14, color: "var(--muted)", margin: 0 }}>
            Nothing is subscribed on this number.
          </p>
        ) : (
          <ul style={{ display: "grid", gap: 10, listStyle: "none", margin: 0, padding: 0 }}>
            {active.map((sub) => (
              <li key={sub.id} className="h-card">
                <p style={{ margin: 0, fontWeight: 700, fontSize: 16 }}>{sub.name}</p>
                <p style={{ margin: "2px 0 0", fontSize: 13, color: "var(--muted)" }}>
                  {sub.merchant} · LKR {sub.price_lkr} · {sub.renewal}
                </p>
                {/* An unconsented charge is the single most common cause in the
                    rule packs, so it is named here rather than left to the
                    customer to discover on their balance. */}
                {!sub.consent ? (
                  <p style={{ margin: "8px 0 0" }}>
                    <Alert tone="warning">
                      This was never confirmed with you. Cancelling it here stops the
                      next charge; ask Clarity to get the past ones looked at.
                    </Alert>
                  </p>
                ) : null}
                <button
                  type="button"
                  className="h-btn h-btn-ghost"
                  style={{ marginTop: 10 }}
                  disabled={busy}
                  onClick={() => setConfirming({ kind: "cancel", subscription: sub })}
                >
                  Cancel {sub.name}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="packages-catalogue">
        <h2
          id="packages-catalogue"
          style={{
            fontSize: 11,
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: ".08em",
            color: "var(--muted)",
            margin: "0 0 10px",
          }}
        >
          Available packs
        </h2>
        {app.catalogue.length === 0 ? (
          <EmptyState
            title="No packs on offer"
            description="The catalogue is empty for this account right now."
          />
        ) : (
          <ul style={{ display: "grid", gap: 10, listStyle: "none", margin: 0, padding: 0 }}>
            {app.catalogue.map((offering) => (
              <li
                key={offering.offering_id}
                className={offering.recommended ? "h-card h-rule-card" : "h-card"}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                  <div>
                    <p style={{ margin: 0, fontWeight: 700, fontSize: 16 }}>{offering.name}</p>
                    <p style={{ margin: "2px 0 0", fontSize: 13, color: "var(--muted)" }}>
                      {offering.data_gb} GB · {offering.validity_days} days · {offering.apps}
                    </p>
                  </div>
                  <p
                    style={{
                      margin: 0,
                      fontWeight: 800,
                      fontSize: 18,
                      whiteSpace: "nowrap",
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    LKR {offering.price_lkr}
                  </p>
                </div>
                <p style={{ margin: "8px 0 0", fontSize: 12, color: "var(--muted)" }}>
                  After the fair-use cap: {offering.after_cap_speed}
                </p>
                <button
                  type="button"
                  className="h-btn h-btn-primary"
                  style={{ marginTop: 10 }}
                  disabled={busy}
                  onClick={() => setConfirming({ kind: "buy", offering })}
                >
                  Buy {offering.name}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <Dialog
        open={confirming !== null}
        onClose={() => setConfirming(null)}
        title={
          confirming?.kind === "buy"
            ? `Buy ${confirming.offering.name}?`
            : confirming
              ? `Cancel ${confirming.subscription.name}?`
              : "Confirm"
        }
        dismissOnBackdrop={false}
        footer={
          <>
            <button type="button" className="h-btn h-btn-ghost" onClick={() => setConfirming(null)}>
              Keep as it is
            </button>
            <button
              type="button"
              className="h-btn h-btn-primary"
              data-autofocus
              disabled={busy}
              onClick={() => void run()}
            >
              {confirming?.kind === "buy" ? "Buy it" : "Cancel it"}
            </button>
          </>
        }
      >
        {confirming?.kind === "buy" ? (
          <p style={{ marginTop: 0 }}>
            LKR {confirming.offering.price_lkr} comes off your balance of LKR{" "}
            {app.balance_lkr}, for {confirming.offering.data_gb} GB over{" "}
            {confirming.offering.validity_days} days. After the fair-use cap your speed
            becomes {confirming.offering.after_cap_speed}. The pack does not renew by
            itself.
          </p>
        ) : confirming ? (
          <p style={{ marginTop: 0 }}>
            {confirming.subscription.merchant} stops charging you LKR{" "}
            {confirming.subscription.price_lkr}. Nothing already charged comes back from
            this: ask Clarity about a past charge and it will look at the records.
          </p>
        ) : null}
        {error ? (
          <div style={{ marginTop: 12 }}>
            <Alert tone="danger">{error}</Alert>
          </div>
        ) : null}
      </Dialog>
    </main>
  );
}
