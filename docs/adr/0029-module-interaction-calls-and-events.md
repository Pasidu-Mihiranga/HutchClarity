# 0029 - Module interaction: public calls for answers, outbox events for side effects

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |
| Deciders | Architecture (plan v1.4); team to ratify |
| Plan references | enterprise-plan/21 §11; 18 §7; 10 §18 |

## Context
After R1 every module has a `public.py`, but modules interact only through direct, in-process calls orchestrated by `case`. The outbox and event envelope exist in `platform/messaging` and no module uses them. That couples modules at runtime: a slow or failing side effect (issuing a receipt, notifying a customer) sits inside the money path's request, a duplicate request can repeat a side effect, and no module can move to its own process without rewiring every caller. Microservice extraction (ADR-0028) needs one agreed rule for how modules talk.

## Decision
1. **Call through `public.py` when the caller needs an answer to continue**: reads, evaluations and commands whose result decides the next step (build a timeline, detect causes, decide, propose, execute a confirmed plan). Allowed call edges are declared in `backend/tests/architecture/test_module_dependencies.py` and plan 21 §11.2, form an acyclic graph, and point from orchestration towards domain logic.
2. **Publish an event through the outbox for everything that reacts to a fact**: receipts, notifications, audit, insights, reconciliation, Autopsy, cache refresh. The event is written in the same transaction as the state change (I7) and named in the past tense (`action.completed`).
3. **Never use an event as a remote command** ("please refund"). Commands go through the owning module's public surface so the caller gets a typed refusal.
4. **Events carry identifiers and minimal facts, never raw PII**: `subscriber_ref`, case, plan and action IDs, amounts as `Money` strings, the policy snapshot hash. A consumer that needs more asks the owning module.
5. **Delivery is at-least-once; consumers are idempotent** (processed-event table keyed by event ID). Ordering is guaranteed per `subscriber_ref` (partition key). Poison events go to a dead-letter queue with an alert.
6. **Schemas are versioned contracts** owned by the producer (`clarity.contracts.events`, `type@vN`), backward compatible within a version; a breaking change is a new version published alongside the old one until consumers move.
7. **Same code, two drivers**: an in-process bus that dispatches after commit (`lite`) and Kafka (`full`, `prod`), both passing one parity suite (ADR-0027).

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Keep direct calls everywhere | Side effects stay inside the money-path request; extraction means rewriting callers |
| Events for everything (including queries) | Turns simple reads into eventual consistency; a decision must be made on a consistent snapshot |
| Shared database between modules | Hidden coupling; breaks schema-per-module (ADR-0013) and independent deployment |

## Consequences
The first migrated flow is receipts consuming `action.completed` (plan 21 §11.5), which also replaces the per-plan lock added for D1 with idempotent consumption. Every new module states in its `MODULE.md` which events it publishes and consumes. Tests for a consumer use the in-process bus with recorded events.

## Compliance
`test_module_dependencies.py` rejects undeclared call edges and cycles; `test_module_boundaries.py` keeps calls on `public.py`; a contract test per event type checks producer and consumer schemas (added with R2a); code review rejects events used as commands.
