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
