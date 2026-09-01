variable "environment" {
  type        = string
  description = "Deployment environment"
}

variable "ecs_cluster_name" {
  type        = string
  description = "ECS cluster monitored by alarms"
}

variable "ecs_service_name" {
  type        = string
  description = "ECS service monitored by alarms"
}

variable "desired_count" {
  type        = number
  description = "Expected number of running ECS tasks"
}

variable "load_balancer_arn_suffix" {
  type        = string
  description = "ALB CloudWatch dimension"
}

variable "target_group_arn_suffix" {
  type        = string
  description = "Target group CloudWatch dimension"
}

variable "database_identifier" {
  type        = string
  description = "RDS instance monitored by alarms"
}

variable "notification_email" {
  type        = string
  description = "Optional alarm subscription address"
  default     = null
  nullable    = true
}

variable "monthly_budget_usd" {
  type        = number
  description = "Monthly AWS cost budget in USD"
  default     = 75

  validation {
    condition     = var.monthly_budget_usd > 0
    error_message = "monthly_budget_usd must be positive."
  }
}
