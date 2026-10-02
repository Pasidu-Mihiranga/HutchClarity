# Development log

Every PR that changes code, contracts, rules, config or deployment adds **one new file** here (AGENTS.md §6). One file per change means parallel developers never get merge conflicts on the log.

- Path: `docs/devlog/YYYY/YYYY-MM-DD-<work-package>-<slug>.md`, e.g. `2026/2026-10-12-R3-actions-db-idempotency.md`
- Template: [../templates/DEVLOG.md](../templates/DEVLOG.md)
- AI agents write the entry for their own work and say so in "Author(s)".
- To read the history in order: `ls docs/devlog/*/ | sort`, or browse by work package with `ls docs/devlog/*/*-C4-*`.
