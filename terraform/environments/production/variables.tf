variable "aws_region" {
  description = "AWS region used by production"
  type        = string
  default     = "eu-west-2"

  validation {
    condition     = var.aws_region == "eu-west-2"
    error_message = "Production must run in eu-west-2."
  }
}

variable "image_uri" {
  description = "CI-verified ECR image URI qualified by registry digest"
  type        = string

  validation {
    condition = can(regex(
      "^[0-9]{12}\\.dkr\\.ecr\\.eu-west-2\\.amazonaws\\.com/nl2sql-agent@sha256:[0-9a-f]{64}$",
      var.image_uri,
    ))
    error_message = "image_uri must be the nl2sql-agent ECR repository qualified by a sha256 digest."
  }
}

variable "vpc_cidr" {
  description = "Production VPC CIDR"
  type        = string
  default     = "10.20.0.0/16"
}

variable "public_subnets" {
  description = "Public ALB subnets keyed by stable names"
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))
}

variable "private_subnets" {
  description = "Private ECS and RDS subnets keyed by stable names"
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))
}

variable "nat_gateway_subnet_key" {
  description = "Public subnet hosting the cost-optimized single NAT Gateway"
  type        = string
}

variable "certificate_arn" {
  description = "ACM certificate ARN for the production HTTPS listener"
  type        = string

  validation {
    condition     = can(regex("^arn:aws:acm:eu-west-2:[0-9]{12}:certificate/", var.certificate_arn))
    error_message = "certificate_arn must be an ACM certificate in eu-west-2."
  }
}

variable "database_instance_class" {
  description = "Production RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "database_multi_az" {
  description = "Whether production RDS uses a synchronous Multi-AZ standby"
  type        = bool
  default     = false
}

variable "database_backup_retention_days" {
  description = "Automated RDS backup retention"
  type        = number
  default     = 7
}

variable "application_secret_arn" {
  description = "Secrets Manager ARN containing LLM provider configuration"
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^arn:aws:secretsmanager:eu-west-2:[0-9]{12}:secret:", var.application_secret_arn))
    error_message = "application_secret_arn must reference Secrets Manager in eu-west-2."
  }
}

variable "database_application_secret_arn" {
  description = "Secrets Manager ARN containing the least-privilege application database password"
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^arn:aws:secretsmanager:eu-west-2:[0-9]{12}:secret:", var.database_application_secret_arn))
    error_message = "database_application_secret_arn must reference Secrets Manager in eu-west-2."
  }
}

variable "database_application_username" {
  description = "Least-privilege PostgreSQL role created by the migration task"
  type        = string
  default     = "nl2sql_app"
}

variable "monthly_budget_usd" {
  description = "Monthly AWS budget threshold"
  type        = number
  default     = 75
}

variable "github_production_subject" {
  description = "Exact immutable GitHub production environment OIDC subject"
  type        = string

  validation {
    condition     = endswith(var.github_production_subject, ":environment:production") && !strcontains(var.github_production_subject, "*")
    error_message = "github_production_subject must be an exact production environment subject without wildcards."
  }
}

variable "desired_count" {
  description = "Number of ECS tasks maintained by the service"
  type        = number
  default     = 2

  validation {
    condition     = var.desired_count >= 2
    error_message = "Production requires at least two application tasks."
  }
}

variable "log_retention_days" {
  description = "CloudWatch application log retention"
  type        = number
  default     = 30
}

variable "alarm_notification_email" {
  description = "Optional operator address subscribed to production alarms"
  type        = string
  default     = null
  nullable    = true
}
