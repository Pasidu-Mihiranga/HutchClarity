"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Alert, Dialog, ErrorState, Field, Input, Skeleton } from "@clarity/ui";
import { supportedLangs, type Lang } from "@clarity/i18n";
import { useLanguage } from "@/components/LanguageProvider";
import { useMe, meClient } from "@/lib/useMe";

/**
 * Account and settings, on the real account (E4).
 *
 * What was here: a hard-coded "07X XXXX XX89", the subtitle "Demo customer",
 * and four menu rows (Notifications, Network status, Terms, Privacy) that were
 * buttons with no `onClick`. Sign out pushed `/login` without telling the API,
 * so the session cookie stayed valid and the next visit was signed in again.
 *
 * Now: the number and name come from `/v1/me/app`, the rows that correspond to
 * a real route write through it, and signing out calls the API that owns the
 * cookie.
 *
 * **Language is two settings, deliberately.** The picker changes this device's
 * display language at once (that is what `LanguageProvider` is for), and also
 * saves it to the account through `/v1/me/preferences`, because the account
 * language is what the backend composes a notification in. A picker that only
 * did the first would leave a Sinhala customer getting English SMS.
 */

const LANG_LABELS: Record<Lang, string> = {
  en: "English",
  si: "සිංහල",
  ta: "தமிழ்",
};

const NOTIFY_OPTIONS: Array<{ value: string; label: string; hint: string }> = [
  { value: "all", label: "Everything", hint: "Every charge, pack and case update" },
  { value: "important", label: "Important only", hint: "Money, caps and case outcomes" },
  { value: "none", label: "Nothing", hint: "We will still answer when you ask" },
];

/** The safeguards the API accepts, with what each one actually does. */
const SAFEGUARDS: Array<{ kind: "data_on_expiry" | "spend_cap" | "vas_confirm" | "usage_alerts"; label: string; hint: string; placeholder: string }> = [
  {
    kind: "spend_cap",
    label: "Monthly spend cap",
    hint: "We stop chargeable extras once you pass this, in LKR.",
    placeholder: "500",
  },
  {
    kind: "data_on_expiry",
    label: "Data after a pack expires",
    hint: "Set to off so later use cannot draw from your main balance.",
    placeholder: "off",
  },
  {
    kind: "vas_confirm",
    label: "Confirm before a subscription charges",
    hint: "Set to on and a new VAS charge needs your confirmation first.",
    placeholder: "on",
  },
  {
    kind: "usage_alerts",
    label: "Usage alerts",
    hint: "Set to on to be told before a fair-use cap slows you down.",
    placeholder: "on",
  },
];

export default function AccountPage() {
  const { lang, setLang } = useLanguage();
  const router = useRouter();
  const { app, loading, error, refresh, act, busy } = useMe();
  const [editing, setEditing] = useState<null | "notify" | "safeguards" | "family" | "network">(null);
  const [familyMsisdn, setFamilyMsisdn] = useState("");
  const [safeguardValues, setSafeguardValues] = useState<Record<string, string>>({});
  const [signingOut, setSigningOut] = useState(false);

  async function signOut() {
    setSigningOut(true);
    try {
      // The cookie is HttpOnly, so only the API can clear it (B4). Pushing
      // /login without this left the session valid.
      await meClient.logout();
    } catch {
      // A failed sign-out still has to leave the screen: the next call will
      // be refused and send them back here.
    } finally {
      router.push("/login");
    }
  }

  async function saveLanguage(next: Lang) {
    setLang(next);
    await act((api) => api.savePreferences({ language: next, notify: app?.notify ?? "important", large_text: app?.large_text ?? false }));
  }

  async function saveNotify(value: string) {
    const ok = await act((api) =>
      api.savePreferences({ language: lang, notify: value, large_text: app?.large_text ?? false }),
    );
    if (ok) setEditing(null);
  }

  async function saveLargeText(value: boolean) {
    await act((api) =>
      api.savePreferences({ language: lang, notify: app?.notify ?? "important", large_text: value }),
    );
  }

  async function addFamily() {
    const ok = await act((api) => api.addFamilyMember(familyMsisdn.trim()));
    if (ok) {
      setFamilyMsisdn("");
      setEditing(null);
    }
  }

  if (loading) {
    return (
      <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
        <p role="status" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>
          Loading your account
        </p>
        <div style={{ display: "grid", gap: 12 }}>
          <Skeleton style={{ height: 88, borderRadius: "var(--radius)" }} />
          <Skeleton style={{ height: 96, borderRadius: "var(--radius)" }} />
        </div>
      </main>
    );
  }

  if (!app) {
    return (
      <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
        <ErrorState
          title="We could not load your account"
          message={error ?? "Please try again in a moment."}
          onRetry={refresh}
        />
      </main>
    );
  }

  const notifyLabel =
    NOTIFY_OPTIONS.find((option) => option.value === app.notify)?.label ?? app.notify;

  const rows: Array<{ label: string; sub: string; onClick: () => void }> = [
    {
      label: "Notifications",
      sub: notifyLabel,
      onClick: () => setEditing("notify"),
    },
    {
      label: "Safeguards",
      sub: `${Object.keys(app.safeguards).length} set`,
      onClick: () => setEditing("safeguards"),
    },
    {
      label: "Family",
      sub: app.family.length ? `${app.family.length} number(s)` : "Nobody added",
      onClick: () => setEditing("family"),
    },
    {
      label: "Network status",
      sub: app.network.status,
      onClick: () => setEditing("network"),
    },
  ];

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "20px 0 8px" }}>
      {error ? (
        <div style={{ marginBottom: 14 }}>
          <Alert tone="danger">{error}</Alert>
        </div>
      ) : null}

      <section aria-labelledby="account-profile" className="h-card" style={{ marginBottom: 14 }}>
        <h1
          id="account-profile"
          style={{
            fontSize: 12,
            textTransform: "uppercase",
            letterSpacing: ".06em",
            color: "var(--muted)",
            margin: "0 0 4px",
            fontWeight: 600,
          }}
        >
          Account
        </h1>
        <p style={{ margin: 0, fontWeight: 700, fontSize: 18, letterSpacing: "-.02em" }}>
          {app.masked}
        </p>
        <p style={{ margin: "2px 0 0", fontSize: 13, color: "var(--muted)" }}>{app.name}</p>
      </section>

      <section aria-labelledby="account-language" className="h-card" style={{ marginBottom: 14 }}>
        <h2
          id="account-language"
          style={{ fontSize: 13, fontWeight: 650, color: "var(--muted)", margin: "0 0 10px" }}
        >
          Language
        </h2>
        <div role="group" aria-labelledby="account-language" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {supportedLangs.map((l) => (
            <button
              key={l}
              type="button"
              aria-pressed={l === lang}
              disabled={busy}
              onClick={() => void saveLanguage(l)}
              style={{
                borderRadius: 999,
                padding: "8px 16px",
                fontSize: 14,
                fontWeight: 650,
                fontFamily: "inherit",
                cursor: "pointer",
                border: l === lang ? "2px solid var(--orange)" : "1px solid var(--line)",
                background: l === lang ? "var(--orange-soft)" : "rgb(var(--c-surface))",
                color: l === lang ? "var(--orange-ink)" : "var(--ink)",
              }}
            >
              {LANG_LABELS[l]}
            </button>
          ))}
        </div>
        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            marginTop: 14,
            fontSize: 14,
            cursor: "pointer",
          }}
        >
          <input
            type="checkbox"
            checked={app.large_text}
            disabled={busy}
            onChange={(event) => void saveLargeText(event.target.checked)}
          />
          Larger text
        </label>
      </section>

      <nav aria-label="Settings" style={{ marginBottom: 14 }}>
        <ul style={{ display: "grid", gap: 8, listStyle: "none", margin: 0, padding: 0 }}>
          {rows.map(({ label, sub, onClick }) => (
            <li key={label}>
              <button
                type="button"
                onClick={onClick}
                style={{
                  width: "100%",
                  textAlign: "left",
                  padding: "14px 16px",
                  borderRadius: "var(--radius-card-sm)",
                  border: "1px solid var(--line)",
                  background: "rgb(var(--c-surface))",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  fontFamily: "inherit",
                  cursor: "pointer",
                }}
              >
                <span>
                  <span style={{ display: "block", fontWeight: 650, fontSize: 15 }}>{label}</span>
                  <span
                    style={{
                      display: "block",
                      fontSize: 13,
                      color: "var(--muted)",
                      marginTop: 1,
                    }}
                  >
                    {sub}
                  </span>
                </span>
                <span
                  style={{ color: "rgb(var(--c-fg-subtle))", fontSize: 18 }}
                  aria-hidden="true"
                >
                  ›
                </span>
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <button
        type="button"
        onClick={() => void signOut()}
        disabled={signingOut}
        className="h-btn h-btn-ghost"
        style={{ width: "100%", marginBottom: 14 }}
      >
        {signingOut ? "Signing out…" : "Sign out"}
      </button>

      {/* I16: the simulated world is labelled. */}
      <p
        style={{
          border: "1px solid rgb(var(--c-primary) / 0.3)",
          borderRadius: "var(--radius-card-sm)",
          background: "var(--orange-soft)",
          padding: "10px 14px",
          fontSize: 13,
          color: "var(--orange-ink)",
          margin: 0,
        }}
      >
        <strong>SIMULATED</strong> - the HUTCH systems behind this account are
        simulated. No real HUTCH account is connected.
      </p>

      <Dialog
        open={editing === "notify"}
        onClose={() => setEditing(null)}
        title="Notifications"
        description="What we message you about. We never message you to sell something."
      >
        <ul style={{ display: "grid", gap: 8, listStyle: "none", margin: 0, padding: 0 }}>
          {NOTIFY_OPTIONS.map((option) => (
            <li key={option.value}>
              <button
                type="button"
                disabled={busy}
                aria-pressed={app.notify === option.value}
                onClick={() => void saveNotify(option.value)}
                style={{
                  width: "100%",
                  textAlign: "left",
                  padding: "12px 14px",
                  borderRadius: "var(--radius-card-sm)",
                  border:
                    app.notify === option.value
                      ? "2px solid var(--orange)"
                      : "1px solid var(--line)",
                  background: "rgb(var(--c-surface))",
                  fontFamily: "inherit",
                  cursor: "pointer",
                }}
              >
                <span style={{ display: "block", fontWeight: 650 }}>{option.label}</span>
                <span style={{ display: "block", fontSize: 13, color: "var(--muted)" }}>
                  {option.hint}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </Dialog>

      <Dialog
        open={editing === "safeguards"}
        onClose={() => setEditing(null)}
        title="Safeguards"
        description="Protections you set and we keep. Each one is recorded against your number."
      >
        <div style={{ display: "grid", gap: 14 }}>
          {SAFEGUARDS.map((safeguard) => {
            const current = app.safeguards[safeguard.kind];
            const shown =
              current && typeof current === "object" && "value" in current
                ? String((current as { value: unknown }).value)
                : "not set";
            return (
              <div key={safeguard.kind}>
                <Field label={safeguard.label} hint={`${safeguard.hint} Now: ${shown}.`}>
                  {(control) => (
                    <Input
                      {...control}
                      placeholder={safeguard.placeholder}
                      value={safeguardValues[safeguard.kind] ?? ""}
                      onChange={(event) =>
                        setSafeguardValues((prev) => ({
                          ...prev,
                          [safeguard.kind]: event.target.value,
                        }))
                      }
                    />
                  )}
                </Field>
                <button
                  type="button"
                  className="h-btn h-btn-ghost"
                  style={{ marginTop: 6 }}
                  disabled={busy || !(safeguardValues[safeguard.kind] ?? "").trim()}
                  onClick={() =>
                    void act((api) =>
                      api.setSafeguard(
                        safeguard.kind,
                        (safeguardValues[safeguard.kind] ?? "").trim(),
                      ),
                    )
                  }
                >
                  Save
                </button>
              </div>
            );
          })}
        </div>
      </Dialog>

      <Dialog
        open={editing === "family"}
        onClose={() => setEditing(null)}
        title="Family"
        description="Numbers you can see the packs and safeguards of. Both numbers must be Hutch."
        footer={
          <>
            <button type="button" className="h-btn h-btn-ghost" onClick={() => setEditing(null)}>
              Cancel
            </button>
            <button
              type="button"
              className="h-btn h-btn-primary"
              disabled={busy || !familyMsisdn.trim()}
              onClick={() => void addFamily()}
            >
              Add
            </button>
          </>
        }
      >
        {app.family.length ? (
          <ul style={{ margin: "0 0 14px", paddingLeft: 20, fontSize: 14 }}>
            {app.family.map((member) => (
              <li key={member.msisdn}>
                {member.name} · {member.masked}
                {member.pack ? ` · ${member.pack}` : ""}
              </li>
            ))}
          </ul>
        ) : (
          <p style={{ marginTop: 0, fontSize: 14, color: "var(--muted)" }}>
            Nobody has been added yet.
          </p>
        )}
        <Field label="Hutch number" hint="We tell you if the number is not on Hutch.">
          {(control) => (
            <Input
              {...control}
              data-autofocus
              inputMode="tel"
              placeholder="07X XXX XXXX"
              value={familyMsisdn}
              onChange={(event) => setFamilyMsisdn(event.target.value)}
            />
          )}
        </Field>
      </Dialog>

      <Dialog
        open={editing === "network"}
        onClose={() => setEditing(null)}
        title="Network status"
        description="For the area this account is registered in."
      >
        <p style={{ marginTop: 0 }}>{app.network.text}</p>
        {app.network.eta ? (
          <p style={{ fontSize: 13, color: "var(--muted)" }}>Expected back: {app.network.eta}</p>
        ) : null}
      </Dialog>
    </main>
  );
}
