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

output "alb_dns_name" {
  description = "DNS name of the staging application load balancer"
  value       = module.alb.dns_name
}

output "alb_target_group_arn" {
  description = "ARN of the staging application target group"
  value       = module.alb.target_group_arn
}

output "alb_security_group_id" {
  description = "ID of the staging ALB security group"
  value       = module.alb.alb_security_group_id
}

output "ecs_task_security_group_id" {
  description = "ID of the staging ECS task security group"
  value       = module.alb.ecs_task_security_group_id
}
