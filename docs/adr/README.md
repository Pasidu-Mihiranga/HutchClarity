# Architecture Decision Records

Decisions that shaped this system, with the alternatives considered and what
each one costs. A decision that is not written down gets re-argued, or quietly
reversed.

| # | Decision | Status |
|---|---|---|
| [0001](0001-yaml-rule-packs-over-python-detectors.md) | Cause rules are YAML rule packs, not Python plugins | Accepted |
| [0002](0002-policy-as-scoped-effective-dated-data.md) | Policy is scoped, effective-dated data with guardrails | Accepted |
| [0003](0003-policy-change-governance.md) | Every policy change has a class, an impact report and two sets of eyes | Accepted |
| [0004](0004-mcp-holds-no-execute-capability.md) | The MCP server holds no capability to execute | Accepted |
| [0005](0005-idempotency-claimed-before-side-effects.md) | An idempotency key is claimed before anything is consumed | Accepted |
| [0006](0006-prototype-runs-with-no-infrastructure.md) | The prototype runs with no infrastructure, behind swappable ports | Accepted |
| [0007](0007-confirmation-tokens-never-leave-the-server.md) | Confirmation tokens are minted and spent server-side | Accepted |
| [0008](0008-risk-signals-derived-from-evidence.md) | Risk signals are derived from evidence, not supplied by callers | Accepted |
| [0009](0009-no-model-configured-by-default.md) | No language model is configured by default | Accepted |
| [0010](0010-identity-is-issued-here-but-federated-later.md) | Clarity issues its own tokens now, behind the interface Keycloak will fill | Accepted |

## Writing one

Status: `Proposed` -> `Accepted` / `Rejected` -> `Superseded by NNNN`. Never
delete an ADR; supersede it. Each one states context, the decision, the
alternatives and why they lost, the consequences, and how compliance is
checked.

The enterprise plan in [`../enterprise-plan/`](../enterprise-plan/README.md) is
the intended design. These records say what was actually decided while
building, and why it sometimes differs.
