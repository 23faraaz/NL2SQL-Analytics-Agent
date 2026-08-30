terraform {
  # I use the S3 bucket created by bootstrap to store this stack's state
  # I pass the bucket name and region during terraform init
  # use_lockfile enables S3-native locking without a separate DynamoDB table
  backend "s3" {
    key          = "global/terraform.tfstate"
    use_lockfile = true
    encrypt      = true
  }
}