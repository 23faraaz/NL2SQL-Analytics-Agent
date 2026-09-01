output "dns_name" {
  description = "DNS name of the application load balancer"
  value       = aws_lb.app.dns_name
}

output "target_group_arn" {
  description = "ARN of the application target group"
  value       = aws_lb_target_group.app.arn
}

output "load_balancer_arn_suffix" {
  description = "CloudWatch dimension suffix for the ALB"
  value       = aws_lb.app.arn_suffix
}

output "target_group_arn_suffix" {
  description = "CloudWatch dimension suffix for the target group"
  value       = aws_lb_target_group.app.arn_suffix
}

output "alb_security_group_id" {
  description = "ID of the ALB security group"
  value       = aws_security_group.alb.id
}

output "ecs_task_security_group_id" {
  description = "ID of the ECS task security group"
  value       = aws_security_group.ecs_tasks.id
}
