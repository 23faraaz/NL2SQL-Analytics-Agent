# I use S3 to centrally store Terraform state
# versioning for recovery
# AES256 encryption and public-access blocking to protect it
# S3-native locking to prevent concurrent Terraform runs modifying the same state
# this bootstrap stack keeps local state because it creates the remote state bucket

# S3 bucket used to store Terraform remote state
resource "aws_s3_bucket" "state" {
  bucket = var.state_bucket_name

  tags = {
    Project   = "nl2sql-agent"
    ManagedBy = "terraform"
    Purpose   = "terraform-state"
  }
}

resource "aws_kms_key" "state" {
  description             = "Encrypts NL2SQL Terraform state"
  enable_key_rotation     = true
  deletion_window_in_days = 30

  tags = {
    Project   = "nl2sql-agent"
    ManagedBy = "terraform"
    Purpose   = "terraform-state"
  }
}

resource "aws_kms_alias" "state" {
  name          = "alias/nl2sql-terraform-state"
  target_key_id = aws_kms_key.state.key_id
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
      kms_master_key_id = aws_kms_key.state.arn
      sse_algorithm     = "aws:kms"
    }

    bucket_key_enabled = true
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

