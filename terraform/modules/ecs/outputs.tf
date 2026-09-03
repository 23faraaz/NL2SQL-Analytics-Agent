output "cluster_name" {
  value       = aws_ecs_cluster.this.name
  description = "ECS cluster name"
}

output "cluster_arn" {
  value       = aws_ecs_cluster.this.arn
  description = "ECS cluster ARN"
}

output "service_name" {
  value       = aws_ecs_service.app.name
  description = "ECS service name"
}

output "service_arn" {
  value       = aws_ecs_service.app.id
  description = "ECS service ARN"
}

output "task_definition_arn" {
  value       = aws_ecs_task_definition.app.arn
  description = "Current Terraform-managed task definition"
}

output "migration_task_definition_arn" {
  value       = aws_ecs_task_definition.migration.arn
  description = "One-off database bootstrap task definition"
}

output "migration_execution_role_arn" {
  value       = aws_iam_role.migration_execution.arn
  description = "Execution role restricted to database bootstrap secrets"
}

output "migration_task_role_arn" {
  value       = aws_iam_role.migration_task.arn
  description = "Runtime role for the database bootstrap task"
}

output "task_execution_role_arn" {
  value       = aws_iam_role.execution.arn
  description = "Task execution role ARN"
}

output "task_role_arn" {
  value       = aws_iam_role.task.arn
  description = "Application task role ARN"
}

output "log_group_name" {
  value       = aws_cloudwatch_log_group.app.name
  description = "Application CloudWatch log group"
}

output "log_group_arn" {
  value       = aws_cloudwatch_log_group.app.arn
  description = "Application CloudWatch log group ARN"
}
