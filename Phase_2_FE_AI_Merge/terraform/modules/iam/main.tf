# IAM Module - Create roles for ECS tasks and EC2

variable "task_name" {
  description = "Name of the task for the IAM role"
  type        = string
}

variable "ecr_repository_arns" {
  description = "ARNs of ECR repositories for pull access"
  type        = list(string)
  default     = []
}

variable "s3_bucket_arns" {
  description = "ARNs of S3 buckets for access"
  type        = list(string)
  default     = []
}

variable "sagemaker_invoke_endpoint_arns" {
  description = "SageMaker endpoint ARNs the task may invoke (sagemaker:InvokeEndpoint)"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags for IAM resources"
  type        = map(string)
  default     = {}
}

# Assume role policy for ECS tasks
data "aws_iam_policy_document" "ecs_task_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

# Task execution role - allows ECS to pull images and write logs
resource "aws_iam_role" "ecs_task_execution_role" {
  name               = "${var.task_name}-ecs-task-execution-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json

  tags = var.tags
}

# Attach the default ECS task execution policy
resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Policy for ECR access
data "aws_iam_policy_document" "ecr_pull_policy" {
  statement {
    effect = "Allow"
    actions = [
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetAuthorizationToken"
    ]
    resources = var.ecr_repository_arns != [] ? var.ecr_repository_arns : ["*"]
  }
}

resource "aws_iam_role_policy" "ecr_pull_policy" {
  name   = "${var.task_name}-ecr-pull-policy"
  role   = aws_iam_role.ecs_task_execution_role.id
  policy = data.aws_iam_policy_document.ecr_pull_policy.json
}

# CloudWatch Logs policy
data "aws_iam_policy_document" "cloudwatch_logs_policy" {
  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["arn:aws:logs:*:*:*"]
  }
}

resource "aws_iam_role_policy" "cloudwatch_logs_policy" {
  name   = "${var.task_name}-cloudwatch-logs-policy"
  role   = aws_iam_role.ecs_task_execution_role.id
  policy = data.aws_iam_policy_document.cloudwatch_logs_policy.json
}

# Task role - for application permissions
resource "aws_iam_role" "ecs_task_role" {
  name               = "${var.task_name}-ecs-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json

  tags = var.tags
}

# S3 access policy if needed
data "aws_iam_policy_document" "s3_access_policy" {
  count = length(var.s3_bucket_arns) > 0 ? 1 : 0

  statement {
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket"
    ]
    resources = concat(
      var.s3_bucket_arns,
      [for arn in var.s3_bucket_arns : "${arn}/*"]
    )
  }
}

resource "aws_iam_role_policy" "s3_access_policy" {
  count  = length(var.s3_bucket_arns) > 0 ? 1 : 0
  name   = "${var.task_name}-s3-access-policy"
  role   = aws_iam_role.ecs_task_role.id
  policy = data.aws_iam_policy_document.s3_access_policy[0].json
}

data "aws_iam_policy_document" "sagemaker_invoke_policy" {
  count = length(var.sagemaker_invoke_endpoint_arns) > 0 ? 1 : 0

  statement {
    effect = "Allow"
    actions = [
      "sagemaker:InvokeEndpoint",
    ]
    resources = var.sagemaker_invoke_endpoint_arns
  }
}

resource "aws_iam_role_policy" "sagemaker_invoke_policy" {
  count  = length(var.sagemaker_invoke_endpoint_arns) > 0 ? 1 : 0
  name   = "${var.task_name}-sagemaker-invoke-policy"
  role   = aws_iam_role.ecs_task_role.id
  policy = data.aws_iam_policy_document.sagemaker_invoke_policy[0].json
}

output "ecs_task_execution_role_arn" {
  description = "ARN of the ECS task execution role"
  value       = aws_iam_role.ecs_task_execution_role.arn
}

output "ecs_task_role_arn" {
  description = "ARN of the ECS task role"
  value       = aws_iam_role.ecs_task_role.arn
}
