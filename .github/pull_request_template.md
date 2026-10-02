## Summary
<!-- What changed and why (1–3 sentences). -->

**Work package:** <!-- e.g. C4 (enterprise-plan/17 §11.2) -->
**Units touched:** <!-- e.g. detection, contracts -->

## Type
- [ ] Feature  - [ ] Fix  - [ ] Contract change  - [ ] Policy artefact (rule/table/config/template)  - [ ] Docs / plan  - [ ] ADR  - [ ] Infra / CI

## Invariants (AGENTS.md §3)
- [ ] No LLM authority over money; amounts come from decisions
- [ ] Money uses `Money`; time uses `Clock`; no hard-coded policy values
- [ ] Layer and module boundaries respected (only `public.py` across modules, no cross-schema SQL)
- [ ] State-changing calls idempotent; events via the outbox
- [ ] No secrets, no real personal data; mocks labelled as simulated
- [ ] No em dash anywhere; commits have one author and no attribution trailers

## Documentation sync (AGENTS.md §5)
- [ ] `MODULE.md` of each touched unit updated
- [ ] New devlog entry: `docs/devlog/YYYY/…`
- [ ] Contracts changed → `CHANGELOG.md` + consumers' `MODULE.md`
- [ ] New unit or dependency → `docs/modules.md` + `ARCHITECTURE.md`
- [ ] Flow changed → walkthrough re-verified (date + commit)
- [ ] Decision made → ADR; plan changed → `enterprise-plan/CHANGES.md`
- [ ] If label `docs-not-needed` is used, the reason is: …

## Tests
<!-- Commands run and their result, including any failures. -->
