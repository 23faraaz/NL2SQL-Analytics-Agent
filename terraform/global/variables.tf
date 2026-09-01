variable "github_oidc_subject" {
  description = "Exact GitHub OIDC subject trusted to publish application images"
  type        = string

  validation {
    condition = (
      startswith(var.github_oidc_subject, "repo:")
      && endswith(var.github_oidc_subject, ":ref:refs/heads/main")
      && !strcontains(var.github_oidc_subject, "*")
      && !strcontains(var.github_oidc_subject, "?")
    )
    error_message = "github_oidc_subject must be an exact main-branch repo subject ending with :ref:refs/heads/main and without wildcards."
  }
}

variable "github_production_subject" {
  description = "Exact immutable GitHub production-environment OIDC subject"
  type        = string

  validation {
    condition = (
      startswith(var.github_production_subject, "repo:")
      && endswith(var.github_production_subject, ":environment:production")
      && !strcontains(var.github_production_subject, "*")
      && !strcontains(var.github_production_subject, "?")
    )
    error_message = "github_production_subject must be an exact production environment subject without wildcards."
  }
}

variable "terraform_state_bucket_name" {
  description = "Bootstrap-created bucket containing production Terraform state"
  type        = string
}

variable "infrastructure_permissions_boundary_arn" {
  description = "Optional pre-existing permission boundary for Terraform roles"
  type        = string
  default     = null
  nullable    = true
}
