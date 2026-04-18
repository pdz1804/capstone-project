variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "rag-pipeline"
}

variable "enable_alb_deletion_protection" {
  description = "Enable deletion protection for ALB"
  type        = bool
  default     = false
}

variable "alb_idle_timeout_seconds" {
  description = "ALB idle timeout in seconds for long-running API requests"
  type        = number
  default     = 1800
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN (same region as ALB). When set, ALB serves HTTPS on 443 and HTTP redirects to HTTPS."
  type        = string
  default     = "arn:aws:acm:us-west-2:381492273521:certificate/17b21a9c-00e5-497e-8f2a-fba1a350c24e"
}

variable "https_listener_ssl_policy" {
  description = "SSL policy for ALB HTTPS listener"
  type        = string
  default     = "ELBSecurityPolicy-TLS13-1-2-2021-06"
}

variable "backend_desired_count" {
  description = "Desired number of backend tasks"
  type        = number
  default     = 2
}

variable "backend_min_capacity" {
  description = "Minimum number of backend tasks"
  type        = number
  default     = 1
}

variable "backend_max_capacity" {
  description = "Maximum number of backend tasks"
  type        = number
  default     = 10
}

variable "backend_cpu_target" {
  description = "Target CPU utilization for backend auto-scaling (%)"
  type        = number
  default     = 70
}

variable "backend_memory_target" {
  description = "Target memory utilization for backend auto-scaling (%)"
  type        = number
  default     = 80
}

variable "frontend_desired_count" {
  description = "Desired number of frontend tasks"
  type        = number
  default     = 2
}

variable "frontend_min_capacity" {
  description = "Minimum number of frontend tasks"
  type        = number
  default     = 1
}

variable "frontend_max_capacity" {
  description = "Maximum number of frontend tasks"
  type        = number
  default     = 5
}

variable "frontend_cpu_target" {
  description = "Target CPU utilization for frontend auto-scaling (%)"
  type        = number
  default     = 70
}

variable "frontend_memory_target" {
  description = "Target memory utilization for frontend auto-scaling (%)"
  type        = number
  default     = 80
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7
}

variable "enable_sagemaker_endpoint" {
  description = "When true, create ECR repo for unified multimodal image and a SageMaker real-time endpoint (see Phase_2_FE_AI_Merge/sagemaker/README.md)"
  type        = bool
  default     = true
}

variable "sagemaker_endpoint_name" {
  description = "SageMaker endpoint name. Default: {project_name}-multimodal-rt"
  type        = string
  default     = ""
}

variable "sagemaker_ecr_repository_name" {
  description = "ECR repository for unified SageMaker image. Default: {project_name}-multimodal-unified"
  type        = string
  default     = ""
}

variable "sagemaker_image_tag" {
  description = "Image tag pushed to ECR for the unified SageMaker container"
  type        = string
  default     = "latest"
}

variable "sagemaker_instance_type" {
  description = "SageMaker hosting instance type"
  type        = string
  default     = "ml.g4dn.xlarge"
}

variable "sagemaker_initial_instance_count" {
  description = "Initial instance count for the SageMaker variant"
  type        = number
  default     = 1
}

variable "sagemaker_autoscaling_min" {
  description = "Minimum instances for SageMaker variant auto scaling"
  type        = number
  default     = 1
}

variable "sagemaker_autoscaling_max" {
  description = "Maximum instances for SageMaker variant auto scaling"
  type        = number
  default     = 3
}

variable "sagemaker_target_invocations_per_instance" {
  description = "Target invocations per instance for SageMaker target tracking"
  type        = number
  default     = 2
}

variable "sagemaker_container_environment" {
  description = "Extra env vars for the unified container (merged with region defaults)"
  type        = map(string)
  default     = {}
}

variable "enable_chatbot_history_tables" {
  description = "Create DynamoDB tables for chat sessions/messages history"
  type        = bool
  default     = true
}

variable "chatbot_sessions_table_name" {
  description = "DynamoDB table name for chat sessions (PK=user_id, SK=session_id)"
  type        = string
  default     = "chatbot-session"
}

variable "chatbot_messages_table_name" {
  description = "DynamoDB table name for chat messages (PK=session_id, SK=message_id)"
  type        = string
  default     = "chatbot-messages"
}

variable "chatbot_history_ttl_enabled" {
  description = "Enable TTL on chatbot history tables"
  type        = bool
  default     = false
}

variable "chatbot_history_ttl_attribute_name" {
  description = "TTL attribute name used when chatbot_history_ttl_enabled=true"
  type        = string
  default     = "expires_at"
}

variable "dynamodb_users_table_arn" {
  description = "Optional existing users DynamoDB table ARN to grant backend access"
  type        = string
  default     = ""
}

variable "dynamodb_users_table_name" {
  description = "Optional users DynamoDB table name for backend env (DYNAMODB_USERS_TABLE)"
  type        = string
  default     = ""
}

variable "dynamodb_quiz_results_table_arn" {
  description = "Optional existing quiz results DynamoDB table ARN to grant backend access"
  type        = string
  default     = ""
}

variable "dynamodb_quiz_results_table_name" {
  description = "Optional quiz results DynamoDB table name for backend env (DYNAMODB_QUIZ_RESULTS_TABLE)"
  type        = string
  default     = ""
}

variable "dynamodb_feedback_table_arn" {
  description = "Optional existing feedback DynamoDB table ARN to grant backend access"
  type        = string
  default     = ""
}

variable "dynamodb_feedback_table_name" {
  description = "Optional feedback DynamoDB table name for backend env (DYNAMODB_FEEDBACK_TABLE)"
  type        = string
  default     = ""
}

variable "dynamodb_app_usage_table_arn" {
  description = "Optional existing app usage DynamoDB table ARN to grant backend access"
  type        = string
  default     = ""
}

variable "dynamodb_app_usage_table_name" {
  description = "Optional app usage DynamoDB table name for backend env (DYNAMODB_APP_USAGE_TABLE)"
  type        = string
  default     = ""
}

variable "dynamodb_knowledge_table_arn" {
  description = "Optional existing knowledge DynamoDB table ARN to grant backend access"
  type        = string
  default     = ""
}

variable "dynamodb_knowledge_table_name" {
  description = "Optional knowledge DynamoDB table name for backend env (DYNAMODB_KNOWLEDGE_TABLE)"
  type        = string
  default     = ""
}

variable "enable_default_admin_bootstrap" {
  description = "Enable backend startup bootstrap for default local admin account"
  type        = bool
  default     = true
}

variable "default_admin_username" {
  description = "Default admin username for backend bootstrap"
  type        = string
  default     = "admin"
}

variable "default_admin_email" {
  description = "Default admin email for backend bootstrap"
  type        = string
  default     = "admin@local.dev"
}

variable "default_admin_password" {
  description = "Default admin password for backend bootstrap"
  type        = string
  default     = "quangphu1804"
}

variable "enable_agentcore_runtime_prep" {
  description = "Prepare infrastructure for Bedrock AgentCore runtime deployment (ECR repository)"
  type        = bool
  default     = true
}

variable "agentcore_runtime_ecr_repository_name" {
  description = "Optional override for AgentCore runtime ECR repository name"
  type        = string
  default     = ""
}

variable "enable_search_cache_serverless" {
  description = "Create ElastiCache Serverless and wire backend cache env vars for ECS"
  type        = bool
  default     = true
}

variable "search_cache_serverless_name" {
  description = "Optional ElastiCache Serverless cache name override. Default: {project_name}-cache"
  type        = string
  default     = ""
}

variable "search_cache_engine" {
  description = "Engine for ElastiCache Serverless cache (redis or valkey depending on provider/account support)"
  type        = string
  default     = "redis"
}

variable "search_cache_major_engine_version" {
  description = "Optional major engine version for ElastiCache Serverless"
  type        = string
  default     = ""
}

variable "search_cache_subnet_ids" {
  description = "Optional subnet IDs for ElastiCache Serverless. Default uses up to three default VPC subnets"
  type        = list(string)
  default     = []
}

variable "search_cache_use_tls" {
  description = "Use TLS redis URL (rediss://) when wiring SEARCH_CACHE_REDIS_URL into ECS backend"
  type        = bool
  default     = true
}

variable "search_cache_ttl_seconds" {
  description = "SEARCH_CACHE_TTL_SECONDS value for backend runtime"
  type        = number
  default     = 600
}

variable "search_cache_key_prefix" {
  description = "SEARCH_CACHE_KEY_PREFIX value for backend runtime"
  type        = string
  default     = "phase2:search:v1"
}

variable "search_cache_redis_connect_timeout_seconds" {
  description = "SEARCH_CACHE_REDIS_CONNECT_TIMEOUT_SECONDS value for backend runtime"
  type        = number
  default     = 2
}

variable "search_cache_redis_read_timeout_seconds" {
  description = "SEARCH_CACHE_REDIS_READ_TIMEOUT_SECONDS value for backend runtime"
  type        = number
  default     = 2
}

variable "search_cache_redis_retry_cooldown_seconds" {
  description = "SEARCH_CACHE_REDIS_RETRY_COOLDOWN_SECONDS value for backend runtime"
  type        = number
  default     = 30
}

variable "enable_waf" {
  description = "Enable AWS WAFv2 Web ACL and associate it with the ALB"
  type        = bool
  default     = false
}

variable "waf_name" {
  description = "Optional WAF Web ACL name override. Default: {project_name}-waf"
  type        = string
  default     = ""
}

variable "waf_rate_limit_requests_per_5_minutes" {
  description = "Rate limit threshold per IP for RateLimitRule"
  type        = number
  default     = 2000
}

variable "waf_enable_logging" {
  description = "Enable CloudWatch logging for WAF"
  type        = bool
  default     = true
}

variable "waf_log_retention_days" {
  description = "CloudWatch log retention for WAF logs"
  type        = number
  default     = 30
}
