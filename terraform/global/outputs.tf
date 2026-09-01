output "ecr_repository_url" {
  description = "URL used to push and pull the NL2SQL application image"
  value       = aws_ecr_repository.app.repository_url
}

output "ecr_repository_arn" {
  description = "ARN of the NL2SQL application ECR repository"
  value       = aws_ecr_repository.app.arn
}

output "ecr_repository_name" {
  description = "Name of the NL2SQL application ECR repository"
  value       = aws_ecr_repository.app.name
}

output "github_oidc_provider_arn" {
  description = "ARN of the GitHub Actions IAM OIDC provider"
  value       = module.github_oidc_provider.arn
}

output "ci_publish_role_arn" {
  description = "ARN assumed by trusted CI to publish application images"
  value       = module.ci_publish_role.role_arn
}

output "terraform_plan_role_arn" {
  description = "Read-only role assumed to create a production Terraform plan"
  value       = module.infrastructure_roles.plan_role_arn
}

output "terraform_apply_role_arn" {
  description = "Production-environment role assumed after approval"
  value       = module.infrastructure_roles.apply_role_arn
}
