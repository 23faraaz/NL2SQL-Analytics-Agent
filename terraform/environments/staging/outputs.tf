output "vpc_id" {
  description = "ID of the staging VPC"
  value       = module.networking.vpc_id
}

output "public_subnet_ids" {
  description = "IDs of the staging public subnets"
  value       = module.networking.public_subnet_ids
}

output "private_subnet_ids" {
  description = "IDs of the staging private subnets"
  value       = module.networking.private_subnet_ids
}
