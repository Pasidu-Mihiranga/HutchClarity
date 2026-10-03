# OpenTofu reference for a Clarity deployment (ADR-0016, X03 issue #44).
#
# A **reference**, not an applied environment. It is here so the deployment
# contract has a shape in infrastructure-as-code terms and so HUTCH can see
# what Clarity expects from a cluster. Nothing in CI runs `tofu apply`: there
# is no target cluster and no credentials, and a plan against a cluster that
# does not exist proves nothing.
#
# `tofu validate` and `tofu fmt -check` do run, which is what catches the
# errors this file can actually have.
#
# REQUIRES HUTCH CONFIRMATION: the cluster, its ingress class, its storage
# class, and whether Clarity runs on Kubernetes or OpenShift (plan 21 section
# 11.1 assumes either).

terraform {
  required_version = ">= 1.6"
  required_providers {
    helm = {
      source  = "opentofu/helm"
      version = "~> 2.13"
    }
    kubernetes = {
      source  = "opentofu/kubernetes"
      version = "~> 2.30"
    }
  }
}

variable "kubeconfig" {
  description = "Path to the kubeconfig for the target cluster."
  type        = string
  default     = "~/.kube/config"
}

variable "namespace" {
  description = "Namespace Clarity is deployed into."
  type        = string
  default     = "clarity"
}

variable "image_tag" {
  description = "The image tag to deploy. Pinned per environment, never 'latest'."
  type        = string
}

variable "profile" {
  description = "Runtime profile: full for a real deployment, prod at HUTCH."
  type        = string
  default     = "full"

  validation {
    # `lite` is the no-infrastructure developer profile. Deploying it to a
    # cluster would run the whole platform against simulated HUTCH systems
    # while looking like a real environment, which is exactly the confusion
    # invariant I16 exists to prevent.
    condition     = contains(["full", "prod"], var.profile)
    error_message = "A deployed environment runs the full or prod profile, never lite."
  }
}

variable "secret_name" {
  description = <<-EOT
    Name of a Secret the cluster already holds, carrying every variable in
    .env.example that is not a dummy. It is created out of band by whatever
    HUTCH uses for secret management, because a secret in state is a secret
    in a backend (I14).
  EOT
  type        = string
}

provider "kubernetes" {
  config_path = var.kubeconfig
}

provider "helm" {
  kubernetes {
    config_path = var.kubeconfig
  }
}

resource "kubernetes_namespace" "clarity" {
  metadata {
    name = var.namespace
  }
}

resource "helm_release" "clarity" {
  name      = "clarity"
  chart     = "${path.module}/../helm/clarity"
  namespace = kubernetes_namespace.clarity.metadata[0].name

  set {
    name  = "image.tag"
    value = var.image_tag
  }

  set {
    name  = "profile"
    value = var.profile
  }

  set {
    name  = "existingSecret"
    value = var.secret_name
  }
}
