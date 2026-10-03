# 2026-10-04 - X03 - Deployment artefacts: image, Helm on kind, OpenTofu

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus) built, ran and wrote this |
| Work package | X03 (issue #44), ADR-0016, plan 21 section 11.1 |
| PR / commit | #44 |
| Units touched | deploy, interfaces/mcp, .github/workflows, tests/unit |

## What changed

- `deploy/docker/Dockerfile`: one multi-stage image for every Python
  deployable, non-root (uid 10001), no build toolchain in the runtime layer.
- `deploy/helm/clarity/`: a chart rendering one Deployment and one Service per
  enabled deployable, with liveness and readiness probes, a read-only root
  filesystem, dropped capabilities and `runAsNonRoot`.
- `deploy/opentofu/`: a reference module. `validate` and `fmt -check` run in
  CI; `plan` and `apply` do not.
- A `deploy` CI job: build, lint, render, create kind, load, install, smoke.
- `/health` on `clarity-mcp`, which did not have one.
- `backend/tests/unit/test_deployment_contract.py`: 8 tests.

## Why

Issue #44 acceptance: the Helm chart installed on kind in CI, smoke tests pass.
ADR-0016 requires one OCI image per deployable, config from the environment,
health probes and no secrets in images.

## Two defects the kind cluster found that nothing else could

1. **`clarity-mcp` crash-looped with `ModuleNotFoundError: No module named
   'mcp'`.** The image installed `[postgres,kafka,otlp]` and the MCP SDK lives
   in its own `mcp` extra. It had never shown up because the `dev` extra pulls
   `mcp` in, so `make check` and every local uvicorn run had it.
2. **`clarity-mcp` had no `/health` route.** With the import fixed the pod
   started, answered 404 to the liveness probe, and Kubernetes killed it in a
   loop. ADR-0016 has required a health probe on every deployable since the
   baseline, and this deployable never had one. A process that starts looks
   healthy until an orchestrator asks it something.

Both are packaging defects invisible to a test suite that imports the code in
one process. That is the argument for the kind job existing.

I also wrote a third defect and caught it before it ran: a comment placed
inside a `\` line continuation in the Dockerfile, which would have commented
out the `pip install` itself.

## Decisions made

1. **One image, four commands.** `clarity-api`, `clarity-mcp`,
   `clarity-channel-gateway` and `hutch-sim` all import the same `clarity`
   package, which is plan 21 section 11.1 scenario S1. Four nearly identical
   images would mean four things to patch when a CVE lands in the base layer.
2. **The chart runs the `lite` profile.** It needs no services (ADR-0006),
   which is what makes a smoke test possible without also standing up
   PostgreSQL, Kafka, Keycloak, OPA and OpenBao inside the cluster. The
   OpenTofu module refuses `lite` with a validation rule, because deploying it
   to a real cluster would run the platform against simulated HUTCH systems
   while looking like a real environment (I16).
3. **No secrets in the chart.** `existingSecret` names a Secret the cluster
   already holds (I14).
4. **The MCP health endpoint is unauthenticated and deliberately empty.** A
   probe runs before any token exists. A health endpoint that listed tools or
   configuration would be free reconnaissance on a server whose whole point is
   that it cannot be driven without a token, so a test asserts the body has
   exactly two keys.
5. **The smoke step checks its output, not its exit status.** `kubectl run`
   exits 0 even when the command inside the pod failed.
6. **OpenTofu is validated, not planned.** There is no target cluster and no
   credentials, so a plan would prove nothing. The README says so rather than
   leaving it to look like an oversight.

## Docs updated

- [x] This devlog entry, `deploy/docker/README.md`, `deploy/opentofu/README.md`
- [ ] CHANGELOG.md - no `/v1` contract change
- [ ] ARCHITECTURE.md - R6/R7 status unchanged; this is the artefact, not the migration

## Tests

```
make check                       1994 passed, 544 skipped
helm lint                        0 charts failed
helm template                    6 objects (3 Deployments, 3 Services)
docker build                     ok, 461MB
kind + helm install --wait       3/3 pods Running
in-cluster /health               api, mcp and channel-gateway all {"status":"ok"}
```

Non-vacuity: removing the `/health` route from the MCP app again fails three of
the new deployment-contract tests.

## Open issues / next step

- `hutch-sim` is in the image and in the README but not in the chart's
  `deployables`. It is a development service and does not belong in a cluster
  that is pretending to be real; adding it would need a profile gate first.
- No Ingress, no HPA, no PodDisruptionBudget, no NetworkPolicy. The chart
  proves the deployment contract; a production topology needs HUTCH's ingress
  class, storage class and network policy model (**REQUIRES HUTCH
  CONFIRMATION**).
- The serverless edges in plan 21 (verify page, PDF rendering, notifications
  fan-out, batch jobs) are not packaged. They need Knative or KEDA on the
  target cluster, which is the same confirmation.
