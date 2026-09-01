output "role_arn" {
  value       = aws_iam_role.this.arn
  description = "Narrow production application release role"
}
