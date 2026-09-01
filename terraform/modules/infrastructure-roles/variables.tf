variable "oidc_provider_arn" {
  type        = string
  description = "GitHub Actions OIDC provider ARN"
}

variable "plan_subject" {
  type        = string
  description = "Exact immutable main-branch subject trusted for planning"
}

variable "apply_subject" {
  type        = string
  description = "Exact immutable production-environment subject trusted for apply"
}

variable "state_bucket_name" {
  type        = string
  description = "S3 bucket containing Terraform state"
}

variable "state_kms_key_arn" {
  type        = string
  description = "Customer-managed KMS key encrypting Terraform state"
}

variable "aws_region" {
  type        = string
  description = "Production AWS region"
  default     = "eu-west-2"
}

variable "permissions_boundary_arn" {
  type        = string
  description = "Pre-existing permission boundary applied to infrastructure roles"
  default     = null
  nullable    = true
}
