# Create an AWS Elastic Container Registry (ECR) repository
# This is where Docker images for the NL2SQL application will be stored
resource "aws_ecr_repository" "app" {

  # Actual repository name that will appear in AWS
  name = "nl2sql-agent"

  # I use immutable tags so a sha tag always points to the same image
  image_tag_mutability = "IMMUTABLE"

  # Keep the repository if it still contains images
  force_delete = false

  # Automatically scan Docker images for known vulnerabilities
  # whenever a new image is pushed to ECR
  image_scanning_configuration {
    scan_on_push = true
  }

  # I use ECR's default AES256 encryption for images at rest
  encryption_configuration {
    encryption_type = "AES256"
  }

  # Tags make the resource easier to identify and manage in AWS
  tags = {
    Project   = "nl2sql-agent"
    ManagedBy = "terraform"
    Purpose   = "container-registry"
  }
}

# Remove unused images so ECR storage does not grow forever
resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Remove untagged images after 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Keep the latest 30 commit images"
        selection = {
          tagStatus      = "tagged"
          tagPatternList = ["sha-*"]
          countType      = "imageCountMoreThan"
          countNumber    = 30
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
