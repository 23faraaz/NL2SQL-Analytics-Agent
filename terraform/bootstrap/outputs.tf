output "state_bucket_name" {
  value = aws_s3_bucket.state.bucket
}

output "state_kms_key_arn" {
  description = "KMS key ARN used by Terraform state backends"
  value       = aws_kms_key.state.arn
}

