variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr must be a valid IPv4 CIDR block."
  }
}

variable "public_subnets" {
  description = "Public subnets keyed by a stable logical name"
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))

  validation {
    condition     = length(var.public_subnets) >= 2
    error_message = "At least two public subnets are required."
  }

  validation {
    condition = alltrue([
      for subnet in values(var.public_subnets) : can(cidrnetmask(subnet.cidr_block))
    ])
    error_message = "Every public subnet must use a valid IPv4 CIDR block."
  }

  validation {
    condition = length(distinct([
      for subnet in values(var.public_subnets) : subnet.cidr_block
    ])) == length(var.public_subnets)
    error_message = "Public subnet CIDR blocks must be unique."
  }

  validation {
    condition = length(distinct([
      for subnet in values(var.public_subnets) : subnet.availability_zone
    ])) == length(var.public_subnets)
    error_message = "Public subnets must use unique Availability Zones."
  }
}

variable "private_subnets" {
  description = "Private subnets keyed by a stable logical name"
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))

  validation {
    condition     = length(var.private_subnets) >= 2
    error_message = "At least two private subnets are required."
  }

  validation {
    condition = alltrue([
      for subnet in values(var.private_subnets) : can(cidrnetmask(subnet.cidr_block))
    ])
    error_message = "Every private subnet must use a valid IPv4 CIDR block."
  }

  validation {
    condition = length(distinct([
      for subnet in values(var.private_subnets) : subnet.cidr_block
    ])) == length(var.private_subnets)
    error_message = "Private subnet CIDR blocks must be unique."
  }

  validation {
    condition = length(distinct([
      for subnet in values(var.private_subnets) : subnet.availability_zone
    ])) == length(var.private_subnets)
    error_message = "Private subnets must use unique Availability Zones."
  }

  validation {
    condition = toset([
      for subnet in values(var.private_subnets) : subnet.availability_zone
      ]) == toset([
      for subnet in values(var.public_subnets) : subnet.availability_zone
    ])
    error_message = "Public and private subnets must use the same Availability Zones."
  }
}

variable "nat_gateway_subnet_key" {
  description = "Key of the public subnet that hosts the NAT Gateway"
  type        = string

  validation {
    condition     = contains(keys(var.public_subnets), var.nat_gateway_subnet_key)
    error_message = "nat_gateway_subnet_key must match a key in public_subnets."
  }
}

variable "environment" {
  description = "Deployment environment name"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]*$", var.environment))
    error_message = "environment must use lowercase letters, numbers or hyphens."
  }
}
