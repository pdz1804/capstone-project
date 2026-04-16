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
  sagemaker_endpoint_effective_name     = trimspace(var.sagemaker_endpoint_name) != "" ? var.sagemaker_endpoint_name : "${var.project_name}-multimodal-rt"
  sagemaker_ecr_repo_effective_name     = trimspace(var.sagemaker_ecr_repository_name) != "" ? var.sagemaker_ecr_repository_name : "${var.project_name}-multimodal-unified"
  agentcore_runtime_ecr_effective_name  = trimspace(var.agentcore_runtime_ecr_repository_name) != "" ? var.agentcore_runtime_ecr_repository_name : "${var.project_name}-agentcore-runtime"
  chatbot_sessions_table_effective_name = trimspace(var.chatbot_sessions_table_name) != "" ? var.chatbot_sessions_table_name : "chatbot-session"
  chatbot_messages_table_effective_name = trimspace(var.chatbot_messages_table_name) != "" ? var.chatbot_messages_table_name : "chatbot-messages"
  search_cache_serverless_name          = trimspace(var.search_cache_serverless_name) != "" ? var.search_cache_serverless_name : "${var.project_name}-cache"
  waf_effective_name                    = trimspace(var.waf_name) != "" ? var.waf_name : "${var.project_name}-waf"
  sagemaker_invoke_arns = var.enable_sagemaker_endpoint ? [
    "arn:aws:sagemaker:${var.aws_region}:${data.aws_caller_identity.current.account_id}:endpoint/${local.sagemaker_endpoint_effective_name}"
  ] : []
  backend_dynamodb_table_arns = compact(concat(
    var.enable_chatbot_history_tables ? [
      aws_dynamodb_table.chatbot_sessions[0].arn,
      aws_dynamodb_table.chatbot_messages[0].arn
    ] : [],
    trimspace(var.dynamodb_users_table_arn) != "" ? [var.dynamodb_users_table_arn] : [],
    trimspace(var.dynamodb_quiz_results_table_arn) != "" ? [var.dynamodb_quiz_results_table_arn] : [],
    trimspace(var.dynamodb_feedback_table_arn) != "" ? [var.dynamodb_feedback_table_arn] : [],
    trimspace(var.dynamodb_app_usage_table_arn) != "" ? [var.dynamodb_app_usage_table_arn] : [],
    trimspace(var.dynamodb_knowledge_table_arn) != "" ? [var.dynamodb_knowledge_table_arn] : []
  ))
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

  search_cache_subnet_ids = length(var.search_cache_subnet_ids) > 0 ? var.search_cache_subnet_ids : slice(
    sort(data.aws_subnets.default.ids),
    0,
    min(3, length(data.aws_subnets.default.ids))
  )
  search_cache_scheme = var.search_cache_use_tls ? "rediss" : "redis"
  search_cache_redis_url = var.enable_search_cache_serverless ? format(
    "%s://%s:%d/0",
    local.search_cache_scheme,
    aws_elasticache_serverless_cache.search_cache[0].endpoint[0].address,
    aws_elasticache_serverless_cache.search_cache[0].endpoint[0].port
  ) : ""
  backend_runtime_env = merge(
    {
      AWS_REGION                     = var.aws_region
      ENABLE_DEFAULT_ADMIN_BOOTSTRAP = tostring(var.enable_default_admin_bootstrap)
      DEFAULT_ADMIN_USERNAME         = var.default_admin_username
      DEFAULT_ADMIN_EMAIL            = var.default_admin_email
      DEFAULT_ADMIN_PASSWORD         = var.default_admin_password
    },
    trimspace(var.dynamodb_users_table_name) != "" ? { DYNAMODB_USERS_TABLE = var.dynamodb_users_table_name } : {},
    trimspace(var.dynamodb_quiz_results_table_name) != "" ? { DYNAMODB_QUIZ_RESULTS_TABLE = var.dynamodb_quiz_results_table_name } : {},
    trimspace(var.dynamodb_feedback_table_name) != "" ? { DYNAMODB_FEEDBACK_TABLE = var.dynamodb_feedback_table_name } : {},
    trimspace(var.dynamodb_app_usage_table_name) != "" ? { DYNAMODB_APP_USAGE_TABLE = var.dynamodb_app_usage_table_name } : {},
    trimspace(var.dynamodb_knowledge_table_name) != "" ? { DYNAMODB_KNOWLEDGE_TABLE = var.dynamodb_knowledge_table_name } : {},
    var.enable_search_cache_serverless ? {
      SEARCH_CACHE_ENABLED                       = "true"
      SEARCH_CACHE_BACKEND                       = "redis"
      SEARCH_CACHE_TTL_SECONDS                   = tostring(var.search_cache_ttl_seconds)
      SEARCH_CACHE_KEY_PREFIX                    = var.search_cache_key_prefix
      SEARCH_CACHE_REDIS_URL                     = local.search_cache_redis_url
      SEARCH_CACHE_REDIS_CONNECT_TIMEOUT_SECONDS = tostring(var.search_cache_redis_connect_timeout_seconds)
      SEARCH_CACHE_REDIS_READ_TIMEOUT_SECONDS    = tostring(var.search_cache_redis_read_timeout_seconds)
      SEARCH_CACHE_REDIS_RETRY_COOLDOWN_SECONDS  = tostring(var.search_cache_redis_retry_cooldown_seconds)
      } : {
      SEARCH_CACHE_ENABLED = "false"
    }
  )
}

resource "aws_security_group" "search_cache" {
  count = var.enable_search_cache_serverless ? 1 : 0

  name        = "${var.project_name}-cache-sg"
  description = "Security group for ElastiCache Serverless search cache"
  vpc_id      = data.aws_vpc.default.id

  tags = {
    Service = "search-cache"
    Name    = "${var.project_name}-cache-sg"
  }
}

resource "aws_elasticache_serverless_cache" "search_cache" {
  count = var.enable_search_cache_serverless ? 1 : 0

  name                 = local.search_cache_serverless_name
  description          = "Serverless cache for retrieval search cache"
  engine               = var.search_cache_engine
  major_engine_version = trimspace(var.search_cache_major_engine_version) != "" ? var.search_cache_major_engine_version : null
  security_group_ids   = [aws_security_group.search_cache[0].id]
  subnet_ids           = local.search_cache_subnet_ids

  tags = {
    Service = "search-cache"
    Name    = local.search_cache_serverless_name
  }
}

resource "aws_dynamodb_table" "chatbot_sessions" {
  count = var.enable_chatbot_history_tables ? 1 : 0

  name         = local.chatbot_sessions_table_effective_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "session_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "session_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  dynamic "ttl" {
    for_each = var.chatbot_history_ttl_enabled ? [1] : []
    content {
      attribute_name = var.chatbot_history_ttl_attribute_name
      enabled        = true
    }
  }

  tags = {
    Service = "chatbot-sessions"
  }
}

resource "aws_dynamodb_table" "chatbot_messages" {
  count = var.enable_chatbot_history_tables ? 1 : 0

  name         = local.chatbot_messages_table_effective_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"
  range_key    = "message_id"

  attribute {
    name = "session_id"
    type = "S"
  }

  attribute {
    name = "message_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  dynamic "ttl" {
    for_each = var.chatbot_history_ttl_enabled ? [1] : []
    content {
      attribute_name = var.chatbot_history_ttl_attribute_name
      enabled        = true
    }
  }

  tags = {
    Service = "chatbot-messages"
  }
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

module "agentcore_runtime_ecr" {
  count  = var.enable_agentcore_runtime_prep ? 1 : 0
  source = "./modules/ecr"

  repository_name       = local.agentcore_runtime_ecr_effective_name
  image_tag_mutability  = "MUTABLE"
  scan_on_push          = true
  image_retention_count = 10

  tags = {
    Service = "agentcore-runtime"
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
  dynamodb_table_arns            = local.backend_dynamodb_table_arns

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
  dynamodb_table_arns            = []

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

module "waf" {
  count  = var.enable_waf ? 1 : 0
  source = "./modules/waf"

  waf_name                          = local.waf_effective_name
  alb_arn                           = module.alb.alb_arn
  rate_limit_requests_per_5_minutes = var.waf_rate_limit_requests_per_5_minutes
  enable_logging                    = var.waf_enable_logging
  log_retention_days                = var.waf_log_retention_days

  tags = {
    Service = "waf"
  }

  depends_on = [module.alb]
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
  backend_environment              = local.backend_runtime_env

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
    module.frontend_iam,
    aws_elasticache_serverless_cache.search_cache
  ]
}

resource "aws_security_group_rule" "search_cache_ingress_from_ecs" {
  count = var.enable_search_cache_serverless ? 1 : 0

  type                     = "ingress"
  from_port                = 6379
  to_port                  = 6379
  protocol                 = "tcp"
  security_group_id        = aws_security_group.search_cache[0].id
  source_security_group_id = module.ecs.ecs_tasks_security_group_id
  description              = "Allow ECS tasks to connect to ElastiCache Serverless on 6379"
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