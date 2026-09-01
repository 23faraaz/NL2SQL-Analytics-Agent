data "aws_iam_policy_document" "assume_role" {
  statement {
    sid     = "GitHubActionsFromExactSubject"
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [var.github_oidc_subject]
    }
  }
}

resource "aws_iam_role" "ci_publisher" {
  name                 = var.role_name
  description          = "Allows trusted main-branch CI to publish immutable application images"
  assume_role_policy   = data.aws_iam_policy_document.assume_role.json
  max_session_duration = 3600

  tags = {
    ManagedBy = "terraform"
    Project   = "nl2sql-agent"
    Purpose   = "ci-ecr-publisher"
  }
}

data "aws_iam_policy_document" "ecr_publish" {
  statement {
    sid       = "AuthenticateToECR"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid    = "PublishOnlyToApplicationRepository"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = [var.ecr_repository_arn]
  }
}

resource "aws_iam_role_policy" "ecr_publish" {
  name   = "publish-nl2sql-image"
  role   = aws_iam_role.ci_publisher.id
  policy = data.aws_iam_policy_document.ecr_publish.json
}
