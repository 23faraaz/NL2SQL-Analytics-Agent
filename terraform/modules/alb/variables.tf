variable "environment" {
  description = "Deployment environment name"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]*$", var.environment))
    error_message = "environment must use lowercase letters, numbers or hyphens."
  }
}

variable "vpc_id" {
  description = "ID of the VPC that hosts the ALB"
  type        = string
}

variable "public_subnet_ids" {
  description = "IDs of public subnets used by the internet-facing ALB"
  type        = list(string)

  validation {
    condition     = length(var.public_subnet_ids) >= 2
    error_message = "The ALB requires at least two public subnets."
  }

  validation {
    condition     = length(distinct(var.public_subnet_ids)) == length(var.public_subnet_ids)
    error_message = "Public subnet IDs must be unique."
  }
}

variable "application_port" {
  description = "Port exposed by the application container"
  type        = number
  default     = 8501

  validation {
    condition     = var.application_port >= 1 && var.application_port <= 65535
    error_message = "application_port must be between 1 and 65535."
  }
}

variable "health_check_path" {
  description = "HTTP path used by the ALB target health check"
  type        = string
  default     = "/_stcore/health"

  validation {
    condition     = startswith(var.health_check_path, "/")
    error_message = "health_check_path must start with a forward slash."
  }
}

variable "allowed_ingress_cidr" {
  description = "IPv4 CIDR allowed to reach the HTTP listener"
  type        = string
  default     = "0.0.0.0/0"

  validation {
    condition     = can(cidrnetmask(var.allowed_ingress_cidr))
    error_message = "allowed_ingress_cidr must be a valid IPv4 CIDR block."
  }
}

variable "enable_deletion_protection" {
  description = "Protect the ALB from deletion"
  type        = bool
  default     = false
}

variable "certificate_arn" {
  description = "ACM certificate ARN used by the required HTTPS listener"
  type        = string

  validation {
    condition     = startswith(var.certificate_arn, "arn:aws:acm:")
    error_message = "certificate_arn must be an ACM certificate ARN."
  }
}

variable "ssl_policy" {
  description = "TLS security policy for the HTTPS listener"
  type        = string
  default     = "ELBSecurityPolicy-TLS13-1-2-2021-06"
}

variable "access_logs_bucket" {
  description = "Optional S3 bucket receiving ALB access logs"
  type        = string
  default     = null
  nullable    = true
}

variable "access_logs_prefix" {
  description = "Prefix used for ALB access log objects"
  type        = string
  default     = "alb"
}
