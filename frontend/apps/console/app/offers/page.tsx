"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Textarea,
} from "@clarity/ui";
import type { OfferView } from "@clarity/sdk";
import { AccessDenied } from "@/components/AccessDenied";
import { PageHeader } from "@/components/PageHeader";
import { useStaffSession } from "@/components/StaffSessionProvider";

/**
 * Offer records: what HUTCH sent to a number (OFFER01).
 *
 * **This page is the authority a customer's fraud check rests on.** A customer
 * pastes a suspicious SMS into the app and is told whether an offer on record
 * for their number matches it. The records are what is on this page, so adding
 * one here makes a matching message read as genuine to whoever pastes it.
 *
 * That is why it is gated on `offer:manage`, which only security admin holds,
 * and why the form says so rather than presenting itself as data entry. It is
 * the same shape of authority as a kill switch: nothing here moves money, and
 * everything here changes what a customer is told.
 *
 * **Append-only, and the page states it.** A recorded offer cannot be edited
 * or deleted: a record a customer's check was decided against must not be
 * rewritable afterwards, or the check proves nothing. A correction is a new
 * record, and both stay visible.
 *
 * No verdict logic lives here. The page records offers and lists them; whether
 * a pasted message matches one is decided by the rules in the offers module
 * (I1), and this page never sees a customer's message at all.
 */
export default function OffersPage() {
  const { client, session, generation, hasPermission } = useStaffSession();
  const canManage = hasPermission("offer:manage");

  const [offers, setOffers] = useState<OfferView[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    msisdn: "",
    title: "",
    body: "",
    offer_code: "",
  });

  const load = useCallback(() => {
    if (!canManage) return;
    void client
      .listOffers()
      .then((found) => {
        setOffers(found);
        setError(null);
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Could not read the offer records"),
      );
  }, [canManage, client]);

  useEffect(load, [load, generation]);

  async function record() {
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const created = await client.recordOffer({
        msisdn: form.msisdn.trim(),
        title: form.title.trim(),
        body: form.body.trim(),
        offer_code: form.offer_code.trim(),
      });
      setStatus(
        `Recorded "${created.title}" against ${created.msisdn_masked}. A message matching it will now read as genuine for that number.`,
      );
      setForm({ msisdn: "", title: "", body: "", offer_code: "" });
      load();
    } catch (e: unknown) {
      // The API's refusal is the message: "no such subscriber" tells the
      // operator what to fix, and rewriting it would hide which rule refused.
      setError(e instanceof Error ? e.message : "The offer was not recorded");
    } finally {
      setBusy(false);
    }
  }

  if (!session || !canManage) {
    return <AccessDenied need="offer:manage" />;
  }

  const ready = form.msisdn.trim() && form.title.trim() && form.body.trim();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Offer records"
        description="What HUTCH sent to a number. A customer pasting a suspicious message into the app is told whether anything here matches it, so these records are what the answer is measured against."
      />

      {error ? <Alert tone="danger">{error}</Alert> : null}
      {status ? <Alert tone="success">{status}</Alert> : null}

      <section aria-labelledby="offers-record">
        <Card className="space-y-3 rounded-card border-line bg-surface shadow-card">
          <h2 id="offers-record" className="font-display text-lg font-semibold">
            Record an offer
          </h2>
          <Alert tone="warning" title="This changes what a customer is told">
            Adding an offer makes a message matching it read as genuine for that
            number. Records cannot be edited or removed afterwards, because a
            check already decided against one must stay decidable the same way;
            a correction is a new record.
          </Alert>

          <div className="grid gap-3 sm:grid-cols-2">
            <Field
              label="Hutch number"
              hint="The subscriber the offer was sent to. Stored as a pseudonym, never as the number."
            >
              {(control) => (
                <Input
                  {...control}
                  inputMode="tel"
                  placeholder="0785720767"
                  value={form.msisdn}
                  onChange={(e) => setForm({ ...form, msisdn: e.target.value })}
                />
              )}
            </Field>
            <Field label="Title" hint="What the campaign is, in a few words.">
              {(control) => (
                <Input
                  {...control}
                  placeholder="Double data on your Anytime pack"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                />
              )}
            </Field>
          </div>

          <Field
            label="The message HUTCH sent"
            hint="Paste it exactly as it went out. This is the text a customer's message is compared against, so wording matters."
          >
            {(control) => (
              <Textarea
                {...control}
                rows={5}
                placeholder="Dear Customer, your Anytime 10GB pack now carries 10GB extra data free for 30 days..."
                value={form.body}
                onChange={(e) => setForm({ ...form, body: e.target.value })}
              />
            )}
          </Field>

          <Field
            label="Offer code (optional)"
            hint="If the SMS carries one. A code is usually copied intact, so it is the strongest single thing to match on."
            className="sm:max-w-xs"
          >
            {(control) => (
              <Input
                {...control}
                placeholder="DD10"
                value={form.offer_code}
                onChange={(e) => setForm({ ...form, offer_code: e.target.value })}
              />
            )}
          </Field>

          <Button disabled={busy || !ready} loading={busy} onClick={() => void record()}>
            Record this offer
          </Button>
        </Card>
      </section>

      <section aria-labelledby="offers-list">
        <Card className="space-y-3 rounded-card border-line bg-surface shadow-card">
          <div className="flex items-center justify-between">
            <h2 id="offers-list" className="font-display text-lg font-semibold">
              On record
            </h2>
            {offers ? <Badge>{offers.length}</Badge> : null}
          </div>

          {offers === null ? (
            <p className="flex items-center gap-2 text-sm text-mute">
              <Spinner size="sm" label="Loading the offer records" />
              Loading…
            </p>
          ) : offers.length === 0 ? (
            <EmptyState
              title="Nothing on record"
              description="Until an offer is recorded, every message a customer checks comes back as not on record."
            />
          ) : (
            <Table
              caption="Offers on record, newest first"
              scrollLabel="Offer records"
              className="text-sm"
            >
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Number</TableHeaderCell>
                  <TableHeaderCell>Title</TableHeaderCell>
                  <TableHeaderCell>Code</TableHeaderCell>
                  <TableHeaderCell>Valid</TableHeaderCell>
                  <TableHeaderCell>Recorded by</TableHeaderCell>
                  <TableHeaderCell>Source</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {offers.map((offer) => (
                  <TableRow key={offer.offer_id}>
                    <TableCell className="font-mono text-xs">{offer.msisdn_masked}</TableCell>
                    <TableCell>
                      <span className="block font-medium">{offer.title}</span>
                      <span className="mt-0.5 block max-w-md text-xs text-mute">
                        {offer.body}
                      </span>
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {offer.offer_code || "—"}
                    </TableCell>
                    <TableCell>
                      <Badge tone={offer.still_valid ? "success" : "neutral"}>
                        {offer.still_valid ? "live" : "expired"}
                      </Badge>
                      <span className="mt-1 block text-xs text-mute">
                        from {new Date(offer.valid_from).toLocaleDateString()}
                        {offer.valid_to
                          ? ` to ${new Date(offer.valid_to).toLocaleDateString()}`
                          : ", no end date"}
                      </span>
                    </TableCell>
                    <TableCell className="text-xs">{offer.recorded_by}</TableCell>
                    <TableCell>
                      {/* I16: a simulated record says so wherever it is shown. */}
                      <Badge tone={offer.source === "hutch-sim" ? "warning" : "neutral"}>
                        {offer.source}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          <p className="text-xs text-fg-muted">
            An expired offer still matches a message: somebody forwarding last
            month&apos;s genuine SMS is not being defrauded, and the answer says
            it was real and has ended rather than that it was never sent.
          </p>
        </Card>
      </section>
    </div>
  );
}
