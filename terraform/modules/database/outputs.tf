output "address" {
  description = "Private RDS endpoint hostname"
  value       = aws_db_instance.this.address
}

output "port" {
  description = "PostgreSQL port"
  value       = aws_db_instance.this.port
}

output "database_name" {
  description = "Initial application database name"
  value       = aws_db_instance.this.db_name
}

output "master_secret_arn" {
  description = "Secrets Manager ARN containing the AWS-managed master credentials"
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}

output "identifier" {
  description = "RDS instance identifier"
  value       = aws_db_instance.this.identifier
}
