terraform {
  backend "s3" {
    bucket         = "nl2sql-terraform-state-faraaz-2026"
    key            = "global/terraform.tfstate"
    region         = "eu-west-2"
    dynamodb_table = "nl2sql-terraform-state-locks"
    encrypt        = true
  }
}