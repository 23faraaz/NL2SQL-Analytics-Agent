variable "aws_region" {
  description = "AWS region used by the staging environment"
  type        = string

  validation {
    condition     = var.aws_region == "eu-west-2"
    error_message = "The staging environment must use eu-west-2."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for the staging VPC"
  type        = string
}

variable "public_subnets" {
  description = "Public staging subnets keyed by logical name"
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))
}

variable "private_subnets" {
  description = "Private staging subnets keyed by logical name"
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))
}

variable "nat_gateway_subnet_key" {
  description = "Key of the public subnet that hosts the staging NAT Gateway"
  type        = string
}

variable "certificate_arn" {
  description = "ACM certificate ARN for the staging HTTPS listener"
  type        = string

  validation {
    condition     = can(regex("^arn:aws:acm:eu-west-2:[0-9]{12}:certificate/", var.certificate_arn))
    error_message = "certificate_arn must be an ACM certificate in eu-west-2."
  }
}
