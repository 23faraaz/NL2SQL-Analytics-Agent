variable "environment" {
  description = "Deployment environment name"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]*$", var.environment))
    error_message = "environment must use lowercase letters, numbers or hyphens."
  }
}

variable "vpc_id" {
  description = "ID of the VPC where RDS will run"
  type        = string
}

variable "private_subnet_ids" {
  description = "IDs of private subnets where RDS may run"
  type        = list(string)

  validation {
    condition     = length(var.private_subnet_ids) >= 2
    error_message = "At least two private subnets are required."
  }

  validation {
    condition = (
      length(distinct(var.private_subnet_ids))
      == length(var.private_subnet_ids)
    )
    error_message = "Private subnet IDs must be unique."
  }
}

variable "ecs_task_security_group_id" {
  description = "ID of the ECS task security group allowed to reach PostgreSQL"
  type        = string
}

variable "database_name" {
  description = "Name of the initial PostgreSQL database"
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z][A-Za-z0-9_]*$", var.database_name))
    error_message = "database_name must begin with a letter and contain only letters, numbers or underscores."
  }
}

variable "database_username" {
  description = "PostgreSQL master username; the password is managed by AWS Secrets Manager"
  type        = string

  validation {
    condition     = length(trimspace(var.database_username)) > 0
    error_message = "database_username must not be empty."
  }
}

variable "instance_class" {
  description = "RDS database instance class selected by the calling environment"
  type        = string

  validation {
    condition     = startswith(var.instance_class, "db.")
    error_message = "instance_class must be a valid RDS class beginning with db."
  }
}

variable "allocated_storage" {
  description = "Initial database storage allocation in GiB"
  type        = numbe

  validation {
    condition = (
      var.allocated_storage >= 20
      && floor(var.allocated_storage) == var.allocated_storage
    )
    error_message = "allocated_storage must be a whole number of at least 20 GiB."
  }
}

variable "multi_az" {
  description = "Whether RDS maintains a synchronous standby in another Availability Zone"
  type        = bool
}

variable "backup_retention_days" {
  description = "Number of days automated database backups are retained"
  type        = numbe

  validation {
    condition = (
      var.backup_retention_days >= 1
      && var.backup_retention_days <= 35
      && floor(var.backup_retention_days) == var.backup_retention_days
    )
    error_message = "backup_retention_days must be a whole number from 1 through 35."
  }
}

variable "deletion_protection" {
  description = "Whether AWS prevents accidental deletion of the database instance"
  type        = bool
}

variable "engine_version" {
  description = "PostgreSQL major/minor engine version"
  type        = string
  default     = "16"
}

variable "max_allocated_storage" {
  description = "Maximum storage autoscaling limit in GiB"
  type        = numbe
  default     = 100

  validation {
    condition     = var.max_allocated_storage >= var.allocated_storage
    error_message = "max_allocated_storage cannot be lower than allocated_storage."
  }
}

variable "log_retention_days" {
  description = "Retention for exported PostgreSQL logs"
  type        = numbe
  default     = 30
}
