# OpenTofu (Terraform) reference stub

Minimal root module for Hutch Clarity deployment artefacts. It uses the
`local` provider to write a marker file so planners can run `tofu init` /
`tofu apply` without cloud credentials.

## Usage

```bash
cd deploy/opentofu
tofu init
tofu apply -auto-approve -var='environment=dev'
```

## Next

- Wire real providers (Azure / AWS / on-prem) behind the same variable surface.
- Keep secrets out of state; inject via the platform secret manager.
- Align resource names with `deploy/helm/clarity` and ADR deployment contract.
