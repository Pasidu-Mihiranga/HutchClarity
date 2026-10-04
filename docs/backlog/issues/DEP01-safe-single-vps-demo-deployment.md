# [DEP01] Safe single-VPS demo deployment

| Field | Value |
|---|---|
| Wave | W5 Frontend and hardening |
| Area | `deploy` |
| Priority | P1 |
| Depends on | X03, FE01, H01, N02 |
| Plan | 21 §5-§7; ADR-0016; ADR-0028 |
| Labels | `wave:w5`, `area:deploy`, `priority:p1`, `type:feature` |

## Scope

- Audit, snapshot, back up and temporarily stop the existing VPS project without deleting any data.
- Package all three Next.js apps and deploy the `full` profile on a private Compose network.
- Publish only the three HTTPS origins through a hardened reverse proxy.
- Persist PostgreSQL, Kafka, Keycloak state and the synthetic receipt signing key.
- Provide health, backup, rollback, HTTPS renewal and server-bootstrap operations.

## Acceptance tests

- The prior project has a validated database dump and exact restart command.
- Customer, Desk and verifier journeys pass over trusted IP HTTPS.
- Internal infrastructure has no public listener.
- A failed first deployment restores the previous project.
- `make check`, frontend builds, Compose validation and live smoke tests pass.

GitHub: #57.
