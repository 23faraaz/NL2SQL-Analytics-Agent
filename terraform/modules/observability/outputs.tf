output "operations_topic_arn" {
  value       = aws_sns_topic.operations.arn
  description = "SNS topic receiving production operational alerts"
}

output "dashboard_name" {
  value       = aws_cloudwatch_dashboard.production.dashboard_name
  description = "CloudWatch operations dashboard"
}
