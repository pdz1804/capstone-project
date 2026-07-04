# SageMaker real-time endpoint for unified container (Docling + Whisper + ColQwen)

variable "endpoint_name" {
  description = "SageMaker endpoint name"
  type        = string
}

variable "variant_name" {
  description = "Production variant name"
  type        = string
  default     = "AllTraffic"
}

variable "image_uri" {
  description = "Full container image URI (ECR)"
  type        = string
}

variable "instance_type" {
  description = "SageMaker hosting instance type"
  type        = string
  default     = "ml.g4dn.xlarge"
}

variable "initial_instance_count" {
  description = "Initial instance count for the variant"
  type        = number
  default     = 1
}

variable "container_environment" {
  description = "Environment variables passed to the container"
  type        = map(string)
  default     = {}
}

variable "autoscaling_min_capacity" {
  description = "Minimum instance count (Application Auto Scaling)"
  type        = number
  default     = 1
}

variable "autoscaling_max_capacity" {
  description = "Maximum instance count (Application Auto Scaling)"
  type        = number
  default     = 3
}

variable "target_invocations_per_instance" {
  description = "Target SageMakerVariantInvocationsPerInstance for target tracking"
  type        = number
  default     = 2
}

variable "tags" {
  description = "Tags for SageMaker and IAM resources"
  type        = map(string)
  default     = {}
}

locals {
  container_rev = substr(sha256(jsonencode({
    image = var.image_uri
    env   = var.container_environment
  })), 0, 12)
  model_name = substr("${var.endpoint_name}-m-${local.container_rev}", 0, 63)
  cfg_name   = substr("${var.endpoint_name}-c-${local.container_rev}", 0, 63)
}

data "aws_iam_policy_document" "sagemaker_assume" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["sagemaker.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "sagemaker_execution" {
  name               = substr("${var.endpoint_name}-sm-exec", 0, 64)
  assume_role_policy = data.aws_iam_policy_document.sagemaker_assume.json

  tags = merge(var.tags, {
    Name = "${var.endpoint_name}-sm-exec"
  })
}

resource "aws_iam_role_policy_attachment" "sagemaker_ecr_read" {
  role       = aws_iam_role.sagemaker_execution.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

data "aws_iam_policy_document" "sagemaker_execution_logs" {
  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]
    resources = ["arn:aws:logs:*:*:log-group:/aws/sagemaker/*"]
  }
}

resource "aws_iam_role_policy" "sagemaker_execution_logs" {
  name   = substr("${var.endpoint_name}-sm-logs", 0, 128)
  role   = aws_iam_role.sagemaker_execution.id
  policy = data.aws_iam_policy_document.sagemaker_execution_logs.json
}

resource "aws_sagemaker_model" "main" {
  name               = local.model_name
  execution_role_arn = aws_iam_role.sagemaker_execution.arn

  primary_container {
    image       = var.image_uri
    environment = var.container_environment
  }

  tags = merge(var.tags, {
    Name = local.model_name
  })
}

resource "aws_sagemaker_endpoint_configuration" "main" {
  name = local.cfg_name

  production_variants {
    variant_name           = var.variant_name
    model_name             = aws_sagemaker_model.main.name
    initial_instance_count = var.initial_instance_count
    instance_type          = var.instance_type
    initial_variant_weight = 1
  }

  tags = merge(var.tags, {
    Name = local.cfg_name
  })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_sagemaker_endpoint" "main" {
  name                 = var.endpoint_name
  endpoint_config_name = aws_sagemaker_endpoint_configuration.main.name

  tags = merge(var.tags, {
    Name = var.endpoint_name
  })
}

resource "aws_appautoscaling_target" "variant" {
  max_capacity       = var.autoscaling_max_capacity
  min_capacity       = var.autoscaling_min_capacity
  resource_id        = "endpoint/${aws_sagemaker_endpoint.main.name}/variant/${var.variant_name}"
  scalable_dimension = "sagemaker:variant:DesiredInstanceCount"
  service_namespace  = "sagemaker"

  depends_on = [aws_sagemaker_endpoint.main]
}

resource "aws_appautoscaling_policy" "invocations" {
  name               = "${var.endpoint_name}-invocations-tracking"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.variant.resource_id
  scalable_dimension = aws_appautoscaling_target.variant.scalable_dimension
  service_namespace  = aws_appautoscaling_target.variant.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "SageMakerVariantInvocationsPerInstance"
    }
    target_value       = var.target_invocations_per_instance
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

output "endpoint_name" {
  value = aws_sagemaker_endpoint.main.name
}

output "endpoint_arn" {
  value = aws_sagemaker_endpoint.main.arn
}

output "execution_role_arn" {
  value = aws_iam_role.sagemaker_execution.arn
}

output "model_name" {
  value = aws_sagemaker_model.main.name
}
