terraform {
  # I store staging state in the bucket created by bootstrap
  # I pass the bucket name and region during terraform init
  backend "s3" {
    key          = "staging/terraform.tfstate"
    use_lockfile = true
    encrypt      = true
  }
}
