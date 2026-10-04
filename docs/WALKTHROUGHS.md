# Walkthroughs

A walkthrough is a **verified, step-by-step tour of a real flow**: what you click, which API is called, which modules run, and what proves it worked. It records "last verified: date + commit" and is re-verified whenever the flow changes ([AGENTS.md §8](../AGENTS.md)). Template: [templates/WALKTHROUGH.md](templates/WALKTHROUGH.md). Files live in [walkthroughs/](walkthroughs/). The demo storyboard for judges is [submission/DEMO_SCRIPT.md](submission/DEMO_SCRIPT.md).

| ID | Walkthrough | Journey / plan ref | Status | Last verified |
|---|---|---|---|---|
| WT-01 | Local setup (`make setup`, `make dev`, `lite` profile) and repository tour | AGENTS.md §13 | to write (flow works) | - |
| WT-02 | [VAS charge without consent → one-tap fix → receipt](walkthroughs/WT-02-vas-journey.md) | 03 §6.1 | verified: the acceptance suite over `/v1` and the browser suite (`frontend/e2e/dispute-charge.spec.ts`), which ran green for the first time in FE01 | 2026-10-04 |
| WT-03 | Duplicate reload → zero-contact refund | 03 §6.2 | to write (flow works) | - |
| WT-04 | "Unlimited" data stopped → explain-only (FUP disclosed) | 03 §6.4 | to write (flow works) | - |
| WT-05 | Large disputed reload → staff approval with step-up, four-eyes above policy threshold | 03 §6.5 | to write (flow works) | - |
| WT-06 | Policy change: scoped cap override with replay impact report and maker-checker | 20 §14 | to write (flow works) | - |
| WT-07 | Receipt QR verification and decision replay | 09 §15 | to write (flow works) | - |
| WT-08 | Adding a new rule pack (golden tests → publish) | 09 §13.4 | to write (flow works) | - |
| WT-09 | Adding a new module (public surface, MODULE.md, boundary test) | 21 §4 | to write (flow works) | - |
| WT-10 | [External MCP client asks "why was I charged?"](walkthroughs/WT-10-external-mcp-client.md) | 07 §10.7 | verified | 2026-10-03 |
| WT-11 | Running the `full` profile | 21 §9 | planned (R2) | - |
| WT-12 | Deploying: containers for the core, serverless edges | 21 §5 | planned (R7) | - |
| WT-13 | [Staff console roles: role switcher, desk, kill switches](walkthroughs/WT-13-staff-console.md) | 18 §5.4 | verified: queue and the four-eyes approval are driven by `frontend/e2e/staff-desk.spec.ts` (FE01) | 2026-10-04 |
| WT-14 | [Audit trail backup and restore runbook](walkthroughs/WT-14-audit-restore-runbook.md) | audit assurance plan Phase 6, ADR-0038 | verified in `lite`; the PostgreSQL drill is written and runs in the `full` CI lane, not yet executed | 2026-10-04 |
| WT-15 | [The console Audit section](walkthroughs/WT-15-console-audit-section.md) | audit assurance plan 5.8, Phase 5 | verified: driven by `frontend/e2e/audit-console.spec.ts` (9 of 9) | 2026-10-04 |
