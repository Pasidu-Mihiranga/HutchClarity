# Container images

One image, several commands. `clarity-api`, `clarity-mcp`,
`clarity-channel-gateway` and `hutch-sim` all import the same `clarity`
package, so they share an image and differ only in the command the orchestrator
runs (plan 21 section 11.1, scenario S1).

```bash
# From the repository root, because the build context includes rules/ and config/.
docker build -f deploy/docker/Dockerfile -t clarity:dev .
```

| Deployable | Command |
|---|---|
| `clarity-api` | `uvicorn clarity.entrypoints.asgi:app --host 0.0.0.0 --port 8000` |
| `clarity-mcp` | `uvicorn clarity.entrypoints.mcp_asgi:app --host 0.0.0.0 --port 8099` |
| `clarity-channel-gateway` | `uvicorn --app-dir services/channel-gateway/src main:app --host 0.0.0.0 --port 8102` |
| `hutch-sim` | `uvicorn --app-dir services/hutch-sim/src main:app --host 0.0.0.0 --port 8103` |

Every one of them answers `GET /health`, which is what the Helm chart's
liveness and readiness probes use (ADR-0016).

`CLARITY_PROFILE` defaults to `full` in the image, because an image is built to
be deployed. A local run against no infrastructure sets `CLARITY_PROFILE=lite`.
