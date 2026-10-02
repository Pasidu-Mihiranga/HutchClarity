# Walkthroughs

A walkthrough is a **verified, step-by-step tour of a real flow**: what you click, which API is called, which modules and events run, and what proves it worked. It is written when the flow is built and re-verified whenever the flow changes (AGENTS.md §8). Template: [templates/WALKTHROUGH.md](templates/WALKTHROUGH.md). Files live in [walkthroughs/](walkthroughs/).

| ID | Walkthrough | Journey / plan ref | Needed by | Status | Last verified |
|---|---|---|---|---|---|
| WT-01 | Local setup (`lite` and `full` profiles, `db-reset`, `.env`) and repository tour | AGENTS.md, ARCHITECTURE.md | G1 baseline | planned | - |
| WT-02 | Adding a new module (from the `_example` template) | 17 §2.1 | G1 baseline | planned | - |
| WT-03 | VAS charge without consent → one-tap fix → receipt | 03 §6.1 | M1 walking skeleton | planned | - |
| WT-04 | Duplicate reload → zero-contact refund | 03 §6.2, 17 §7.3 | M3 | planned | - |
| WT-05 | "Unlimited" data stopped → explain-only (FUP disclosed) | 03 §6.4 | M3 | planned | - |
| WT-06 | Large disputed reload → staff approval with step-up MFA | 03 §6.5 | M3 | planned | - |
| WT-07 | Proactive bill-shock warning → spend cap safeguard | 03 §6.6 | M3 | planned | - |
| WT-08 | WhatsApp voice note in Tamil → one-tap fix | 03 §6.3 | M3 | planned | - |
| WT-09 | Policy change: campaign cap override with replay and approval | 19 §14 A | M3 | planned | - |
| WT-10 | External MCP client asks "why was I charged?" | 07 §10.7, 17 §10 | M3 | planned | - |
| WT-11 | Receipt QR verification and decision replay | 09 §15 | M3 | planned | - |
| WT-12 | Adding a new cause detector (teach once → golden tests → publish) | 09 §13.4, 19 | M3 | planned | - |
| WT-13 | Deploying to a VPS, AWS, Azure and Kubernetes | 18 §2, deploy/ | M4 | planned | - |
| WT-SC | Staff console roles (demo role switcher, desk, kill switches) — [WT-02-staff-console.md](walkthroughs/WT-02-staff-console.md) | 17 §5.4 | M1 staff surface | verified | 2026-10-02 |
