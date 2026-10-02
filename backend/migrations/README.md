# Per-module Alembic migrations

Each Clarity domain module owns **one Postgres schema** and **one Alembic
revision history**. There is no single root `alembic/` tree for the whole
monolith.

## Layout

```text
backend/migrations/
  README.md                 ← this file
  case/
    alembic.ini
    env.py                  ← copy from platform/db/alembic_env_template.py
    versions/
  actions/
    ...
  platform/
    ...
```

## Rules

1. Set `MODULE_SCHEMA` in `env.py` to the module schema name (`case`, `actions`, …).
2. Store Alembic's `alembic_version` table **inside that schema**
   (`version_table_schema=MODULE_SCHEMA`).
3. Never edit a merged revision; add a new one (expand → migrate → contract).
4. Application code must not join across module schemas (ADR schema-per-module).
5. `make db-reset` (when wired) recreates schemas and runs every module's
   `upgrade head`.

## Bootstrap a module

```bash
mkdir -p backend/migrations/case/versions
cp backend/src/clarity/platform/db/alembic_env_template.py \
   backend/migrations/case/env.py
# edit MODULE_SCHEMA = "case" and wire target_metadata to the module models
# add alembic.ini pointing script_location at this folder
alembic -c backend/migrations/case/alembic.ini revision -m "init" --autogenerate
alembic -c backend/migrations/case/alembic.ini upgrade head
```

Until a module has real models, keep an empty `versions/` directory; the
template is enough for reviewers to see the intended contract.
