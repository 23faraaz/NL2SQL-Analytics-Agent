# Create an AWS Elastic Container Registry (ECR) repository
# This is where Docker images for the NL2SQL application will be stored
resource "aws_ecr_repository" "app" {

  # Actual repository name that will appear in AWS
  name = "nl2sql-agent"

  # Allows an existing image tag such as "latest" or "v1"
  # to be moved to a newer image
  image_tag_mutability = "MUTABLE"

  # Automatically scan Docker images for known vulnerabilities
  # whenever a new image is pushed to ECR
  image_scanning_configuration {
    scan_on_push = true
  }

  # Tags make the resource easier to identify, organise, and track in AWS
  tags = {
    Project   = "nl2sql-agent"
    ManagedBy = "terraform"
    Purpose   = "container-registry"
  }
}