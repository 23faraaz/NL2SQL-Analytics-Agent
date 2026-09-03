output "ecs_cluster_name" {
  value       = module.ecs.cluster_name
  description = "Production ECS cluster name"
}

output "ecs_service_name" {
  value       = module.ecs.service_name
  description = "Production ECS service name"
}

output "ecs_task_definition_arn" {
  value       = module.ecs.task_definition_arn
  description = "Terraform-managed task definition revision"
}

output "database_migration_task_definition_arn" {
  value       = module.ecs.migration_task_definition_arn
  description = "One-off database bootstrap task definition"
}

output "dataset_release_bucket_name" {
  value       = aws_s3_bucket.dataset_releases.id
  description = "Private versioned Olist dataset release bucket"
}

output "dataset_release_kms_key_arn" {
  value       = aws_kms_key.dataset_releases.arn
  description = "Customer-managed KMS key encrypting Olist dataset releases"
}

output "dataset_importer_task_definition_arn" {
  value       = module.ecs.importer_task_definition_arn
  description = "One-off Olist importer task definition"
}

output "data_import_role_arn" {
  value       = aws_iam_role.data_import.arn
  description = "GitHub OIDC role restricted to the production importer task"
}

output "ecs_private_subnet_ids" {
  value       = module.networking.private_subnet_ids
  description = "Private subnets used by application and migration tasks"
}

output "ecs_task_security_group_id" {
  value       = module.alb.ecs_task_security_group_id
  description = "Security group used by application and migration tasks"
}

output "ecs_task_execution_role_arn" {
  value       = module.ecs.task_execution_role_arn
  description = "ECS task execution role used for image, log, and secret access"
}

output "ecs_task_role_arn" {
  value       = module.ecs.task_role_arn
  description = "Application task role"
}

output "health_check_url" {
  value       = "https://${module.alb.dns_name}/_stcore/health"
  description = "Production health endpoint through the ALB"
}

output "alb_target_group_arn" {
  value       = module.alb.target_group_arn
  description = "Production ALB target group"
}

output "application_log_group_name" {
  value       = module.ecs.log_group_name
  description = "Application CloudWatch log group"
}

output "operations_dashboard_name" {
  value       = module.observability.dashboard_name
  description = "CloudWatch operations dashboard"
}

output "database_master_secret_arn" {
  value       = module.database.master_secret_arn
  description = "Master credential secret used only by controlled database administration and migrations"
  sensitive   = true
}

output "application_deploy_role_arn" {
  value       = module.application_deploy_role.role_arn
  description = "GitHub OIDC role used only for production ECS application releases"
}
