# Hutch Clarity — OpenTofu / Terraform reference stub
#
# This module does not provision real cloud resources yet. It writes a local
# marker file so `tofu init && tofu apply` succeeds in CI and demos.
#
# Replace the null / local_file placeholder with HUTCH platform modules
# (network, Postgres, Kafka, Keycloak, OPA, object storage) when the
# deployment contract (ADR-0006) is implemented for prod.

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}

variable "environment" {
  type        = string
  description = "Target environment label (dev / staging / prod)."
  default     = "dev"
}

resource "local_file" "clarity_marker" {
  filename = "${path.module}/.clarity-opentofu-${var.environment}.marker"
  content  = <<-EOT
    Hutch Clarity OpenTofu placeholder
    environment = ${var.environment}
    version     = 0.2.0-baseline
  EOT
}

output "marker_path" {
  value = local_file.clarity_marker.filename
}
