output "arn" {
  description = "ARN of the GitHub Actions IAM OIDC provider"
  value       = aws_iam_openid_connect_provider.github.arn
}
