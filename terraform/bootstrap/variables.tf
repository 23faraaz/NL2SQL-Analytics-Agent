variable "state_bucket_name" {
  type        = string
  description = "Name of the S3 bucket used for Terraform state"
}

variable "lock_table_name" {
  type        = string
  description = "Name of the DynamoDB table used for Terraform state locking"
}
