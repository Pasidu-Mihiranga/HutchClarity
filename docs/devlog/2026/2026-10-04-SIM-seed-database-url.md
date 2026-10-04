# 2026-10-04 - SIM - `make seed` writes to DATABASE_URL again

| Field | Value |
|---|---|
| Author(s) | KusalPabasara; agent: Claude Code (Claude Opus 5.5) wrote the change and this entry |
| Work package | hutch-sim data, DEP01 #57 follow-up |
| PR / commit | branch `fix/seed-database-url` |
| Units touched | `backend/scripts/seed.py` |

## What changed
- `seed.py` calls `configure(os.environ.get("DATABASE_URL"))` before touching the store.

## Why
B07 made the store driver stop reading the environment; the composition root tells it which database to use. `seed.py` was never updated, so `make seed` with a PostgreSQL `DATABASE_URL` silently seeded `./clarity_world.db` instead. Found while reseeding the VPS for the 078 numbers: in the read-only API container the SQLite fallback could not be created, so it failed loudly and wrote nothing.

## Decisions made
- The script is an entry point, so reading `DATABASE_URL` there is the same as the composition root doing it; the driver still never reads the environment.

## Docs updated
- [ ] None: `deploy/README.md` already documents the reseed command

## Tests
- Piped into Python with `DATABASE_URL=sqlite:///<tmp>/target.db`: seeds 44 customers into `target.db`, and no `clarity_world.db` fallback appears.
- VPS: backup `clarity-20261004T063826Z.sql.gz`, then the reseed through the API container: `Seeded 44 customers, 5 knowledge articles, 2000 historical complaints.` `healthcheck.sh` passes. Over public HTTPS, `+94781234567` signs in as Dilani, `+94771234567` is not found, and the Desk queue, Autopsy and Foresight answer 200.
- `ruff check` and `ruff format --check` pass.

## Open issues / next step
- None.
