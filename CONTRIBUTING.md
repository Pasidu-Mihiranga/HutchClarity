# Contributing to Hutch Clarity

Read [AGENTS.md](AGENTS.md) first. It holds the invariants, the documentation sync matrix and the glossary that every contributor (human or AI agent) follows. This file covers the day-to-day workflow.

## 1. Before you start a task
1. Pick a work package from [17 §11.2](docs/enterprise-plan/17-build-blueprint.md) and check its dependencies in [17 §13.1](docs/enterprise-plan/17-build-blueprint.md).
2. Read the unit's `MODULE.md` and the contracts it uses.
3. If the task needs a contract change, a new dependency between modules, or a decision not covered by an ADR, **raise it first** (contract PR or ADR). Don't change another team's module silently.

## 2. Branches and commits
- Branch from `main`: `feat/<wp>-<slug>`, `fix/<module>-<slug>`, `docs/<slug>`, `adr/<nnnn>-<slug>`.
- Commit rules are in [AGENTS.md §10.1](AGENTS.md): one author (your GitHub user), no co-author or AI attribution, Conventional Commits subject, optional short `- ` bullets only.
- Keep PRs small (one work-package step). Unfinished features stay behind feature flags; `main` is always releasable.

## 3. Pull requests
- Fill in the PR template completely.
- Required checks after scaffolding (A1): lint, types, import rules, tests, contract tests, security scans. Reviewers check documentation sync, commit rules and the no-em-dash rule.
- Reviews: CODEOWNERS. Money-path paths (`modules/actions`, `modules/decision`, `modules/receipts`, `rules/`, `services/signer`) need **two** approvals.
- Merge with squash; the squash title and body follow the same commit rules.

## 4. Changing shared things

| Change | Process |
|---|---|
| Contract (`contracts/`) | Contract PR → consumers approve → semver bump → `CHANGELOG.md` → regenerate types → implement |
| Architecture or technology decision | ADR (Proposed) → review → Accepted → then code |
| The plan (`docs/enterprise-plan/`) | ADR if it's a decision → edit chapters → entry in [`docs/enterprise-plan/CHANGES.md`](docs/enterprise-plan/CHANGES.md) → bump the plan version |
| Policy artefact (detector, decision table, parameter, template) | Lifecycle in [19](docs/enterprise-plan/19-policy-change-management.md): golden tests + replay report + approvals for its change class |
| New module / service / app | Copy [`docs/templates/MODULE.md`](docs/templates/MODULE.md); register in [`docs/modules.md`](docs/modules.md) and [`ARCHITECTURE.md`](ARCHITECTURE.md) |

## 5. Documentation every PR
The sync matrix in [AGENTS.md §5](AGENTS.md) is mandatory. Reviewers reject PRs that skip it.

## 6. Definition of done
See [AGENTS.md §11](AGENTS.md).

## 7. Releases
- Semantic Versioning: `v0.x` during the build, `v1.0.0` at milestone M4 ([17 §14](docs/enterprise-plan/17-build-blueprint.md)).
- The **final hackathon submission** is a signed annotated tag (e.g. `v1.0.0-submission`) whose commit matches the demo and the submitted documents.
