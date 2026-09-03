variable "environment" {
  type        = string
  description = "Deployment environment"
}

variable "aws_region" {
  type        = string
  description = "AWS region used by the task"
}

variable "image_uri" {
  type        = string
  description = "Immutable ECR image URI"

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.image_uri))
    error_message = "image_uri must be qualified by a sha256 registry digest."
  }
}

variable "ecr_repository_arn" {
  type        = string
  description = "ARN of the application ECR repository"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnets used by Fargate tasks"

  validation {
    condition     = length(distinct(var.private_subnet_ids)) >= 2
    error_message = "ECS requires at least two unique private subnets."
  }
}

variable "security_group_id" {
  type        = string
  description = "Security group attached to ECS tasks"
}

variable "target_group_arn" {
  type        = string
  description = "ALB target group for the application"
}

variable "database_host" {
  type        = string
  description = "Private database hostname"
}

variable "database_port" {
  type        = number
  description = "Database port"
}

variable "database_name" {
  type        = string
  description = "Application database name"
}

variable "database_username" {
  type        = string
  description = "Application database username"
}

variable "database_secret_arn" {
  type        = string
  description = "Secrets Manager ARN containing the database password"
}

variable "database_master_secret_arn" {
  type        = string
  description = "AWS-managed RDS master secret used only by the migration task"
}

variable "application_secret_arn" {
  type        = string
  description = "Secrets Manager ARN containing application provider configuration"
}

variable "desired_count" {
  type        = number
  description = "Desired ECS task count"
  default     = 2
}

variable "minimum_count" {
  type        = number
  description = "Minimum autoscaled task count"
  default     = 2
}

variable "maximum_count" {
  type        = number
  description = "Maximum autoscaled task count"
  default     = 4

  validation {
    condition     = var.maximum_count >= var.minimum_count
    error_message = "maximum_count cannot be lower than minimum_count."
  }
}

variable "cpu" {
  type        = number
  description = "Fargate CPU units"
  default     = 512
}

variable "memory" {
  type        = number
  description = "Fargate memory in MiB"
  default     = 1024
}

variable "application_port" {
  type        = number
  description = "Application container port"
  default     = 8501
}

variable "health_check_path" {
  type        = string
  description = "Container health-check path"
  default     = "/_stcore/health"
}

variable "log_retention_days" {
  type        = number
  description = "CloudWatch log retention"
  default     = 30
}
