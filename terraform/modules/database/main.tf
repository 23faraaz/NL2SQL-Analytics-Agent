locals {
  common_tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
    Project     = "nl2sql-agent"
  }
}

resource "aws_security_group" "database" {
  name_prefix = "${var.environment}-database-"
  description = "Allows PostgreSQL only from the ECS application tasks"
  vpc_id      = var.vpc_id

  tags = merge(local.common_tags, {
    Name = "${var.environment}-database-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "postgres_from_ecs" {
  security_group_id            = aws_security_group.database.id
  description                  = "PostgreSQL from ECS tasks"
  referenced_security_group_id = var.ecs_task_security_group_id
  from_port                    = 5432
  ip_protocol                  = "tcp"
  to_port                      = 5432
}

resource "aws_vpc_security_group_egress_rule" "ecs_to_postgres" {
  security_group_id            = var.ecs_task_security_group_id
  description                  = "PostgreSQL to the application database"
  referenced_security_group_id = aws_security_group.database.id
  from_port                    = 5432
  ip_protocol                  = "tcp"
  to_port                      = 5432
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.environment}-nl2sql"
  subnet_ids = var.private_subnet_ids

  tags = merge(local.common_tags, {
    Name = "${var.environment}-nl2sql-db-subnets"
  })
}

resource "aws_cloudwatch_log_group" "postgresql" {
  name              = "/aws/rds/instance/${var.environment}-nl2sql/postgresql"
  retention_in_days = var.log_retention_days
  skip_destroy      = false

  tags = local.common_tags
}

resource "aws_db_instance" "this" {
  identifier = "${var.environment}-nl2sql"

  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  db_name  = var.database_name
  username = var.database_username
  port     = 5432

  manage_master_user_password = true

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.database.id]
  publicly_accessible    = false

  multi_az                = var.multi_az
  backup_retention_period = var.backup_retention_days
  backup_window           = "02:00-03:00"
  maintenance_window      = "sun:03:00-sun:04:00"

  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.environment}-nl2sql-final"
  copy_tags_to_snapshot     = true

  auto_minor_version_upgrade = true
  apply_immediately          = false

  enabled_cloudwatch_logs_exports = ["postgresql"]
  performance_insights_enabled    = true

  depends_on = [aws_cloudwatch_log_group.postgresql]

  tags = local.common_tags
}
