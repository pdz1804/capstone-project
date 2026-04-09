terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.25"
    }
  }

  # Uncomment to use S3 backend for storing terraform state
  # backend "s3" {
  #   bucket         = "your-terraform-state-bucket"
  #   key            = "phase2-fe-ai-merge/terraform.tfstate"
  #   region         = "us-west-2"
  #   encrypt        = true
  #   dynamodb_table = "terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = var.environment
      Project     = var.project_name
      ManagedBy   = "Terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

locals {
  sagemaker_endpoint_effective_name = trimspace(var.sagemaker_endpoint_name) != "" ? var.sagemaker_endpoint_name : "${var.project_name}-multimodal-rt"
  sagemaker_ecr_repo_effective_name = trimspace(var.sagemaker_ecr_repository_name) != "" ? var.sagemaker_ecr_repository_name : "${var.project_name}-multimodal-unified"
  sagemaker_invoke_arns = var.enable_sagemaker_endpoint ? [
    "arn:aws:sagemaker:${var.aws_region}:${data.aws_caller_identity.current.account_id}:endpoint/${local.sagemaker_endpoint_effective_name}"
  ] : []
  sagemaker_default_env = merge(
    {
      AWS_REGION                     = var.aws_region
      UNIFIED_MAX_CONCURRENT_GPU_OPS = "1"
      COLQWEN_MODEL                  = "vidore/colqwen2-v1.0"
      COLQWEN_QUANTIZATION           = "8bit"
      WHISPER_MODEL                  = "base"
      DOCLING_OCR_ENGINE             = "rapidocr"
      DOCLING_ENABLE_VLM             = "false"
      DOCLING_ENABLE_OCR             = "true"
      DOCLING_EXPORT_IMAGES          = "false"
      DOCLING_EXPORT_TABLES          = "false"
      DOCLING_EXPORT_METADATA        = "true"
    },
    var.sagemaker_container_environment
  )
}

module "backend_ecr" {
  source = "./modules/ecr"

  repository_name       = "${var.project_name}-backend"
  image_tag_mutability  = "MUTABLE"
  scan_on_push          = true
  image_retention_count = 10

  tags = {
    Service = "backend"
  }
}

module "frontend_ecr" {
  source = "./modules/ecr"

  repository_name       = "${var.project_name}-frontend"
  image_tag_mutability  = "MUTABLE"
  scan_on_push          = true
  image_retention_count = 10

  tags = {
    Service = "frontend"
  }
}

module "sagemaker_unified_ecr" {
  count  = var.enable_sagemaker_endpoint ? 1 : 0
  source = "./modules/ecr"

  repository_name       = local.sagemaker_ecr_repo_effective_name
  image_tag_mutability  = "MUTABLE"
  scan_on_push          = true
  image_retention_count = 10

  tags = {
    Service = "sagemaker-unified"
  }
}

module "backend_iam" {
  source = "./modules/iam"

  task_name           = "${var.project_name}-backend"
  ecr_repository_arns = [module.backend_ecr.repository_arn]
  s3_bucket_arns      = []

  sagemaker_invoke_endpoint_arns = local.sagemaker_invoke_arns

  tags = {
    Service = "backend"
  }
}

module "frontend_iam" {
  source = "./modules/iam"

  task_name                      = "${var.project_name}-frontend"
  ecr_repository_arns            = [module.frontend_ecr.repository_arn]
  s3_bucket_arns                 = []
  sagemaker_invoke_endpoint_arns = []

  tags = {
    Service = "frontend"
  }
}

module "alb" {
  source = "./modules/alb"

  alb_name   = "${var.project_name}-alb"
  vpc_id     = data.aws_vpc.default.id
  subnet_ids = data.aws_subnets.default.ids

  enable_deletion_protection = var.enable_alb_deletion_protection

  certificate_arn           = var.acm_certificate_arn
  https_listener_ssl_policy = var.https_listener_ssl_policy

  tags = {
    Service = "load-balancer"
  }
}

module "ecs" {
  source = "./modules/ecs"

  cluster_name = "${var.project_name}-cluster"

  vpc_id                = data.aws_vpc.default.id
  subnet_ids            = data.aws_subnets.default.ids
  alb_security_group_id = module.alb.alb_security_group_id

  backend_target_group_arn  = module.alb.backend_target_group_arn
  frontend_target_group_arn = module.alb.frontend_target_group_arn

  ecs_task_execution_role_arn = module.backend_iam.ecs_task_execution_role_arn
  ecs_task_role_arn           = module.backend_iam.ecs_task_role_arn

  frontend_task_execution_role_arn = module.frontend_iam.ecs_task_execution_role_arn
  frontend_task_role_arn           = module.frontend_iam.ecs_task_role_arn

  backend_config = {
    name           = "backend"
    image_uri      = "${module.backend_ecr.repository_url}:latest"
    port           = 5000
    cpu            = 512
    memory         = 1024
    desired_count  = var.backend_desired_count
    min_capacity   = var.backend_min_capacity
    max_capacity   = var.backend_max_capacity
    container_name = "backend-container"
  }

  frontend_config = {
    name           = "frontend"
    image_uri      = "${module.frontend_ecr.repository_url}:latest"
    port           = 3000
    cpu            = 256
    memory         = 512
    desired_count  = var.frontend_desired_count
    min_capacity   = var.frontend_min_capacity
    max_capacity   = var.frontend_max_capacity
    container_name = "frontend-container"
  }

  log_retention_days = var.log_retention_days

  tags = {
    Service = "ecs"
  }

  depends_on = [
    module.alb,
    module.backend_iam,
    module.frontend_iam
  ]
}

module "sagemaker_unified" {
  count  = var.enable_sagemaker_endpoint ? 1 : 0
  source = "./modules/sagemaker_endpoint"

  endpoint_name                   = local.sagemaker_endpoint_effective_name
  image_uri                       = "${module.sagemaker_unified_ecr[0].repository_url}:${var.sagemaker_image_tag}"
  instance_type                   = var.sagemaker_instance_type
  initial_instance_count          = var.sagemaker_initial_instance_count
  container_environment           = local.sagemaker_default_env
  autoscaling_min_capacity        = var.sagemaker_autoscaling_min
  autoscaling_max_capacity        = var.sagemaker_autoscaling_max
  target_invocations_per_instance = var.sagemaker_target_invocations_per_instance

  tags = {
    Service = "sagemaker-unified"
  }
}

module "backend_autoscaling" {
  source = "./modules/autoscaling"

  cluster_name = module.ecs.cluster_name
  service_name = module.ecs.backend_service_name

  alb_resource_label = "${module.alb.alb_arn_suffix}/${module.alb.backend_target_group_arn_suffix}"

  min_capacity = var.backend_min_capacity
  max_capacity = var.backend_max_capacity

  cpu_target_tracking_desired_value    = var.backend_cpu_target
  memory_target_tracking_desired_value = var.backend_memory_target

  scale_out_cooldown = 60
  scale_in_cooldown  = 300

  tags = {
    Service = "backend"
  }

  depends_on = [module.ecs]
}

module "frontend_autoscaling" {
  source = "./modules/autoscaling"

  cluster_name = module.ecs.cluster_name
  service_name = module.ecs.frontend_service_name

  alb_resource_label = "${module.alb.alb_arn_suffix}/${module.alb.frontend_target_group_arn_suffix}"

  min_capacity = var.frontend_min_capacity
  max_capacity = var.frontend_max_capacity

  cpu_target_tracking_desired_value    = var.frontend_cpu_target
  memory_target_tracking_desired_value = var.frontend_memory_target

  scale_out_cooldown = 60
  scale_in_cooldown  = 300

  tags = {
    Service = "frontend"
  }

  depends_on = [module.ecs]
}