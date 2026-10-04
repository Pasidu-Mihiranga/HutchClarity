# Demo script - Hutch Clarity

Hosted synthetic demo endpoints: customer `https://116.203.101.73/`, Clarity
Desk `https://116.203.101.73:8443/`, and Trust Receipt verifier
`https://116.203.101.73:9443/`. These IP endpoints use short-lived trusted TLS
and contain synthetic data only. The local commands below remain the fallback.

Target 5–6 minutes (Guidelines §10 allows 3–7). Based on the storyboard in
plan §42.5.

```bash
make setup         # once
make web-install   # once
make dev           # API on :8000
make web           # the three apps: :3000 customer, :3001 console, :3002 verify
```

Open <http://localhost:3000/>. Click **Reset demo data** on the Desk
(<http://localhost:3001/desk>) before recording, so balances start clean.

> Keep the orange banner visible throughout: *all HUTCH systems are mocked and
> every customer, charge and payment is synthetic*. Say it out loud once too.

---

## 0:00–0:45 - The problem

Show the deck's quotes (slide 2) or say them:

> "The bank took 3,500 for my 90-day pack twice. My Hutch balance is still zero."
> "I recharged and didn't buy anything - the money was deducted anyway."

**Say:** Customers can see *that* money went. They cannot see *why*. The facts
exist, but they are split across payment, charging, catalogue, consent and
usage logs, so nobody can assemble them in a conversation.

**Then:** Explain every rupee. Fix it by rule. Prove it won't happen again.

## 0:45–2:15 - Journey 1: a charge with no consent

Pick **VAS charged with no consent** (Dilani, Sinhala).

A sign-in step appears: the code sits in a panel labelled **simulated SMS
inbox**, because nobody can receive a real SMS in a demo. Enter it.

**Say in one line:** the code is simulated, the check is not - a case holds
someone's charges, so holding its link is not enough to open it. Type a wrong
code first if there is time; it is refused, and attempts are capped.

Then click **ඇයි?** and point out, in this order:

1. **The cause** - `VAS_NO_CONSENT` version 4, 90% confidence, LKR 49.00.
2. **The evidence** - the charge from the charging source, and the *absence* of an OTP in the consent log. Absence is the evidence here.
3. **All eight sources reporting in**, each with its completeness.
4. **What it wasn't** - duplicate reload, FUP cap, pack expiry burn, all explicitly ruled out.
5. **The explanation is in Sinhala**, because that is her language.

**Say:** A rule decided this, not a model. The wording is a template, and any
model-written wording would be checked against these facts before she saw it.

Click **මෙම නිවැරදි කිරීම තහවුරු කරන්න** (Confirm this fix). Three things happen
in one tap: refund, subscription off, merchant blocked.

## 2:15–3:00 - The proof

The Trust Receipt appears. Point out:

- **Balance 263.00 → 312.00**, the real before and after.
- **Recurrence test: PASSED** - and stress this: *it re-read the live state. It did not assume the block worked because the command was accepted.*
- **Signed Ed25519, chain intact.**

Scan the QR (or open `:3002/r/TR-2027-000001`). The public page verifies it
with nothing secret - the same check a customer, an agent on 1788, or TRCSL can
run.

**Optional, strong:** open `:3002/r/TR-2027-999999` - a receipt that was never
issued does not verify: *"No receipt numbered TR-2027-999999 has ever been
issued."* It says that rather than passing or failing the signature, because
there is no document to check.

## 3:00–3:40 - Journey 2: fixed before she noticed

Back to **My Hutch** → **Reload taken twice** → **Why?**

**AUTO FIX.** LKR 3,500 refunded with no contact at all.

**Say:** This is the only path with no human in the loop, and it is deliberately
the narrowest one: money back only, nothing switched off, high confidence,
inside the cap, and the rule explicitly whitelisted. Anything else needs a tap
or a supervisor.

## 3:40–4:30 - Journey 3 and 4: knowing when *not* to act

**'Unlimited' hit a fair-use cap** → **EXPLAIN ONLY.** Nothing was charged
wrongly; the cap was shown at purchase. A receipt is still issued.

**Say:** Refunding here would be wrong. Clarity knows the difference.

**Large reload not credited** → **STAFF APPROVAL**, because of a SIM swap two
days ago. Open the Desk on `:3001/desk`, show the queue sorted by money at
stake, open the case, **Approve as supervisor**.

If showing the intelligence loop, open `:3001/autopsy` and point out
**SYNTHETIC DATA**, **HYPOTHESIS**, masked examples and the honest trigram
diagnostic. Then open `:3001/foresight`: the seeded aggregate personas are
compared with the statistical baseline using LOW/MEDIUM/HIGH bands, while the
screen states **SCENARIO, NOT CERTAINTY** and **NOT CALIBRATED**.

## 4:30–5:15 - The boundary

Open `/v1/mcp/tools`:

```
L1  explain_rule, get_case_timeline, get_cause_assessment,
    get_customer_safeguards, get_trust_receipt
L2  request_handoff
L3  propose_action
```

**Say:** This is every tool an AI agent can call. There is no execute tool. The
strongest thing a model can do is *propose*, and `propose_action` takes an
action type but **no amount** - the amount comes from the decision record.
Confirmation is minted outside the model.

Open `/v1/ai/usage`: **0 tokens, 100% LLM-free.** The deck says Clarity works
without the LLM; this is that running.

If there is time, the other boundary: on the **Desk**, sign in as `agent-9`
with *agent* only and try to approve Priya's LKR 12,000 case - refused, the
role does not carry high-value approval. Sign in as `sup-2`, *supervisor*,
without ticking step-up - refused, it needs recent re-authentication. Tick it
and it goes through, with the approval recorded against the signed-in name
rather than anything the browser claimed.

## 5:15–6:00 - Close

- 300+ tests, `ruff` and `mypy --strict` clean.
- Four journeys end to end on mocked HUTCH systems.
- The 52-section enterprise plan in `docs/enterprise-plan/` takes it from here to production.

**Close on:** From "we don't know" to "here is your receipt."

---

## If something fails live

| Problem | Do this |
|---|---|
| State looks wrong | **Reset demo data**, on either page |
| Port busy | `uvicorn ... --port 8001` |
| A journey already ran | Reset, or use a different customer |
| Browser cached an old page | Hard reload |

Nothing in the demo needs the network. There are no outbound calls.
