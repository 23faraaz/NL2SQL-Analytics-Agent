resource "aws_s3_bucket" "dataset_releases" {
  bucket = "production-nl2sql-datasets-${data.aws_caller_identity.current.account_id}"

  tags = merge(local.common_tags, { Purpose = "dataset-releases" })
}

resource "aws_s3_bucket_versioning" "dataset_releases" {
  bucket = aws_s3_bucket.dataset_releases.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "dataset_releases" {
  bucket = aws_s3_bucket.dataset_releases.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "dataset_releases" {
  bucket = aws_s3_bucket.dataset_releases.id

  rule {
    bucket_key_enabled = true
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "dataset_releases" {
  bucket = aws_s3_bucket.dataset_releases.id

  rule {
    id     = "expire-noncurrent-dataset-releases"
    status = "Enabled"
    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

data "aws_iam_policy_document" "data_import_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [var.github_production_subject]
    }
  }
}

resource "aws_iam_role" "data_import" {
  name                 = "nl2sql-agent-production-data-import"
  description          = "Runs only the approved production Olist importer task"
  assume_role_policy   = data.aws_iam_policy_document.data_import_assume.json
  max_session_duration = 3600
  tags                 = merge(local.common_tags, { Purpose = "dataset-import" })
}

data "aws_iam_policy_document" "data_import" {
  statement {
    sid       = "InspectVersionedDatasetRelease"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:GetObjectAttributes", "s3:GetObjectVersion"]
    resources = ["${aws_s3_bucket.dataset_releases.arn}/releases/*"]
  }

  statement {
    sid       = "RunExactImporterRevision"
    effect    = "Allow"
    actions   = ["ecs:RunTask"]
    resources = [module.ecs.importer_task_definition_arn]

    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [module.ecs.cluster_arn]
    }
  }

  statement {
    sid       = "InspectImportTask"
    effect    = "Allow"
    actions   = ["ecs:DescribeTasks"]
    resources = ["*"]

    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [module.ecs.cluster_arn]
    }
  }

  statement {
    sid     = "PassOnlyImporterRoles"
    effect  = "Allow"
    actions = ["iam:PassRole"]
    resources = [
      module.ecs.migration_execution_role_arn,
      module.ecs.importer_task_role_arn,
    ]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "data_import" {
  name   = "run-production-olist-import"
  role   = aws_iam_role.data_import.id
  policy = data.aws_iam_policy_document.data_import.json
}
