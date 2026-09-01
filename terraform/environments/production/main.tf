data "aws_caller_identity" "current" {}

locals {
  github_oidc_provider_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"
}

data "aws_ecr_repository" "app" {
  name = "nl2sql-agent"
}

resource "aws_s3_bucket" "alb_logs" {
  bucket = "production-nl2sql-alb-logs-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_public_access_block" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  rule {
    id     = "expire-access-logs"
    status = "Enabled"

    filter {}

    expiration {
      days = 90
    }
  }
}

data "aws_iam_policy_document" "alb_logs" {
  statement {
    sid       = "AllowALBLogDelivery"
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.alb_logs.arn}/alb/AWSLogs/${data.aws_caller_identity.current.account_id}/*"]

    principals {
      type        = "Service"
      identifiers = ["logdelivery.elasticloadbalancing.amazonaws.com"]
    }
  }
}

resource "aws_s3_bucket_policy" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id
  policy = data.aws_iam_policy_document.alb_logs.json

  depends_on = [aws_s3_bucket_public_access_block.alb_logs]
}

module "networking" {
  source = "../../modules/networking"

  environment            = local.environment
  vpc_cidr               = var.vpc_cidr
  public_subnets         = var.public_subnets
  private_subnets        = var.private_subnets
  nat_gateway_subnet_key = var.nat_gateway_subnet_key
}

module "alb" {
  source = "../../modules/alb"

  environment                = local.environment
  vpc_id                     = module.networking.vpc_id
  public_subnet_ids          = module.networking.public_subnet_ids
  certificate_arn            = var.certificate_arn
  enable_deletion_protection = true
  access_logs_bucket         = aws_s3_bucket.alb_logs.id

  depends_on = [aws_s3_bucket_policy.alb_logs]
}

module "database" {
  source = "../../modules/database"

  environment                = local.environment
  vpc_id                     = module.networking.vpc_id
  private_subnet_ids         = module.networking.private_subnet_ids
  ecs_task_security_group_id = module.alb.ecs_task_security_group_id
  database_name              = "nl2sql_ecommerce"
  database_username          = "nl2sql_admin"
  instance_class             = var.database_instance_class
  allocated_storage          = 20
  max_allocated_storage      = 100
  multi_az                   = var.database_multi_az
  backup_retention_days      = var.database_backup_retention_days
  deletion_protection        = true
  log_retention_days         = var.log_retention_days
}

module "ecs" {
  source = "../../modules/ecs"

  environment            = local.environment
  aws_region             = var.aws_region
  image_uri              = var.image_uri
  ecr_repository_arn     = data.aws_ecr_repository.app.arn
  private_subnet_ids     = module.networking.private_subnet_ids
  security_group_id      = module.alb.ecs_task_security_group_id
  target_group_arn       = module.alb.target_group_arn
  database_host          = module.database.address
  database_port          = module.database.port
  database_name          = module.database.database_name
  database_username      = var.database_application_username
  database_secret_arn    = var.database_application_secret_arn
  application_secret_arn = var.application_secret_arn
  desired_count          = var.desired_count
  log_retention_days     = var.log_retention_days
}

module "observability" {
  source = "../../modules/observability"

  environment              = local.environment
  ecs_cluster_name         = module.ecs.cluster_name
  ecs_service_name         = module.ecs.service_name
  desired_count            = var.desired_count
  load_balancer_arn_suffix = module.alb.load_balancer_arn_suffix
  target_group_arn_suffix  = module.alb.target_group_arn_suffix
  database_identifier      = module.database.identifier
  notification_email       = var.alarm_notification_email
  monthly_budget_usd       = var.monthly_budget_usd
}

module "application_deploy_role" {
  source = "../../modules/application-deploy-role"

  oidc_provider_arn         = local.github_oidc_provider_arn
  github_production_subject = var.github_production_subject
  cluster_arn               = module.ecs.cluster_arn
  service_arn               = module.ecs.service_arn
  target_group_arn          = module.alb.target_group_arn
  ecr_repository_arn        = data.aws_ecr_repository.app.arn
  task_execution_role_arn   = module.ecs.task_execution_role_arn
  task_role_arn             = module.ecs.task_role_arn
  log_group_arn             = module.ecs.log_group_arn
}
