# OpenTofu reference

A reference module, not an applied environment (ADR-0016).

It exists so the deployment contract has a shape in infrastructure-as-code
terms, and so HUTCH can see what Clarity expects from a cluster: a namespace, a
pinned image tag, a profile that is never `lite`, and a Secret the cluster
already holds.

```bash
tofu -chdir=deploy/opentofu init -backend=false
tofu -chdir=deploy/opentofu validate
tofu -chdir=deploy/opentofu fmt -check
```

CI runs those three. It does **not** run `plan` or `apply`: there is no target
cluster and no credentials, and a plan against a cluster that does not exist
proves nothing. The Helm chart is the part that is actually proven, on `kind`,
in the same workflow.

**REQUIRES HUTCH CONFIRMATION:** the cluster, its ingress class, its storage
class, and whether Clarity runs on Kubernetes or OpenShift.
