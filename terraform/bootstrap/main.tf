# I use S3 to centrally store Terraform state
# versioning for recovery
# AES256 encryption and public-access blocking to protect it
# DynamoDB locking to prevent concurrent Terraform runs from modifying the same state

# S3 bucket used to store Terraform remote state
resource "aws_s3_bucket" "state" {
  bucket = var.state_bucket_name

  tags = {
    Project   = "nl2sql-agent"
    ManagedBy = "terraform"
    Purpose   = "terraform-state"
  }
}

# Keep previous versions of the state file
resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Encrypt Terraform state at rest using S3-managed AES256 encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Prevent the Terraform state bucket from becoming publicly accessible
resource "aws_s3_bucket_public_access_block" "state" {
  bucket = aws_s3_bucket.state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# DynamoDB table used for Terraform state locking
resource "aws_dynamodb_table" "lock" {
  name         = var.lock_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    Project   = "nl2sql-agent"
    ManagedBy = "terraform"
    Purpose   = "terraform-state-locking"
  }
}
