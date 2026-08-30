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
