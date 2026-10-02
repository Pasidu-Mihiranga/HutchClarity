# Backend load / soak notes

Load scripts live with the repo root `tests/load/` tree so k6 (and later
artillery) stay language-agnostic and do not need `PYTHONPATH`.

## Smoke

```bash
# API must be up (make dev-new or make dev)
k6 run tests/load/smoke.js
```

`smoke.js` hits `GET /health` with a small VUs budget. Extend with journeyed
scenarios (open case → evaluate → propose) only after auth stubs are stable.

## Full profile

Point `BASE_URL` at the compose-published API and set `CLARITY_FULL=1` when
exercising Kafka/Valkey-backed paths. Do not run destructive workloads against
shared environments.
