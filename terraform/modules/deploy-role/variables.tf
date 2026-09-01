variable "oidc_provider_arn" {
  description = "ARN of the GitHub Actions IAM OIDC provider"
  type        = string
}

variable "github_oidc_subject" {
  description = "Exact GitHub OIDC subject allowed to publish images"
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

variable "ecr_repository_arn" {
  description = "ARN of the only ECR repository the CI role may publish to"
  type        = string
}

variable "role_name" {
  description = "Name of the CI image-publishing IAM role"
  type        = string
  default     = "nl2sql-agent-github-ci-publisher"
}
