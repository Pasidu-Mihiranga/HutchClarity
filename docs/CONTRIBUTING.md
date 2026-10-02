# Contributing to Hutch Clarity

Read [AGENTS.md](../AGENTS.md) first for invariants and the documentation sync
matrix. This file covers the day-to-day workflow.

## 1. Before you start

1. Check the living architecture and the module `MODULE.md` you will touch.
2. Prefer small PRs (one work-package step). Unfinished features stay behind
   flags; `main` should stay releasable.
3. If the task needs a new module dependency or a decision not covered by an
   ADR, raise an ADR first.

## 2. Branches and commits

- Branch from `main`: `feat/<slug>`, `fix/<module>-<slug>`, `docs/<slug>`,
  `adr/<nnnn>-<slug>`.
- Conventional Commits subject; one author (your GitHub user); no AI
  co-author trailers (see AGENTS.md).
- No em dash (U+2014) in commits, docs or UI text.

## 3. Local checks

```bash
make up-lite          # Postgres
make lint types test  # legacy tree
make test-g1          # backend/src G1 + unit
make dev-new          # modular monolith API on :8000
```

CI jobs: `lint`, `test-legacy`, `test-new`, `gitleaks` (continue-on-error),
`sbom` placeholder.

## 4. Pull requests

- Fill the PR template.
- Reviewers check documentation sync, money-path care, and the no-em-dash rule.
- Squash merge; squash title follows the same commit rules.

## 5. Releases

Semantic versioning: `0.x` during the build, `1.0` at submission. See
`VERSION` and `scripts/tag_baseline.sh` for annotated tag commands (do not tag
casually).
