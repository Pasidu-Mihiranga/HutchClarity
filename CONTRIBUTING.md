# Contributing to Hutch Clarity

Read [AGENTS.md](AGENTS.md) first: invariants, the documentation sync matrix, commit rules and the glossary that every contributor (person or AI agent) follows. This file covers the day-to-day workflow.

## 1. Before you start
1. Find your migration step or work package in [plan 21 §7](docs/enterprise-plan/21-migration-and-deployment-plan.md) and the module in [docs/modules.md](docs/modules.md).
2. Read that module's `MODULE.md` and its `public.py`.
3. If the task changes a module's public surface, a `/v1` contract, or needs a decision no ADR covers, **raise it first** (PR or ADR). Do not change another module's internals.

## 2. Setup
`make setup` then `make check`. Only Python is needed (`lite` profile).

## 3. Branches and commits
- Branch from `main`: `feat/<step>-<slug>`, `fix/<module>-<slug>`, `docs/<slug>`, `adr/<nnnn>-<slug>`.
- Commit rules: [AGENTS.md §10.1](AGENTS.md) (one author, your own GitHub user; no co-author or AI attribution; Conventional Commits subject; optional short `- ` bullets only).
- Keep PRs small; unfinished features stay behind feature flags; `main` is always releasable.

## 4. Pull requests
- Fill in the PR template completely.
- `make check` must pass: lint, types, import contracts, module-boundary tests, all tests.
- CODEOWNERS review; money-path paths (`modules/actions`, `modules/decision`, `modules/receipts`, `rules/`, `config/policy/`) need **two** approvals.
- Squash merge; the squash message follows the same commit rules.

## 5. Changing shared things

| Change | Process |
|---|---|
| A module's public surface or a `/v1` contract | Discuss in the PR → update consumers → `CHANGELOG.md` → consumers' `MODULE.md` |
| Architecture or technology decision | ADR (Proposed) → review → Accepted → then code |
| The plan | ADR if it is a decision → edit chapters → [CHANGES.md](docs/enterprise-plan/CHANGES.md) → plan README revision row |
| Rule pack, decision table, policy value or template | Lifecycle in [plan 20](docs/enterprise-plan/20-policy-change-management.md): golden tests, replay impact report, approvals for its change class |
| New module | Copy [docs/templates/MODULE.md](docs/templates/MODULE.md), add `public.py`, register in [docs/modules.md](docs/modules.md) and [ARCHITECTURE.md](ARCHITECTURE.md) |

## 6. Definition of done
[AGENTS.md §11](AGENTS.md).

## 7. Releases
Semantic Versioning: `v0.x` during the migration, `v1.0.0` at milestone M3 (plan 21 §8). The final hackathon submission is an annotated tag (for example `v1.0.0-submission`) whose commit matches the demo and the submitted documents.
