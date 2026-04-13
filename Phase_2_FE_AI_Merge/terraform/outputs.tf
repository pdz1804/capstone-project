output "backend_ecr_repository_url" {
  description = "Backend ECR repository URL"
  value       = module.backend_ecr.repository_url
}

output "frontend_ecr_repository_url" {
  description = "Frontend ECR repository URL"
  value       = module.frontend_ecr.repository_url
}

output "sagemaker_unified_ecr_repository_url" {
  description = "ECR repository URL for unified SageMaker image (empty if SageMaker disabled)"
  value       = try(module.sagemaker_unified_ecr[0].repository_url, "")
}

output "agentcore_runtime_ecr_repository_url" {
  description = "ECR repository URL for Bedrock AgentCore runtime image (empty if prep disabled)"
  value       = try(module.agentcore_runtime_ecr[0].repository_url, "")
}

output "chatbot_sessions_table_name" {
  description = "DynamoDB chat sessions table name (empty if disabled)"
  value       = try(aws_dynamodb_table.chatbot_sessions[0].name, "")
}

output "chatbot_sessions_table_arn" {
  description = "DynamoDB chat sessions table ARN (empty if disabled)"
  value       = try(aws_dynamodb_table.chatbot_sessions[0].arn, "")
}

output "chatbot_messages_table_name" {
  description = "DynamoDB chat messages table name (empty if disabled)"
  value       = try(aws_dynamodb_table.chatbot_messages[0].name, "")
}

output "chatbot_messages_table_arn" {
  description = "DynamoDB chat messages table ARN (empty if disabled)"
  value       = try(aws_dynamodb_table.chatbot_messages[0].arn, "")
}

output "alb_dns_name" {
  description = "DNS name of the load balancer"
  value       = module.alb.alb_dns_name
}

output "alb_arn" {
  description = "ARN of the load balancer"
  value       = module.alb.alb_arn
}

output "alb_zone_id" {
  description = "Zone ID of the load balancer"
  value       = module.alb.alb_zone_id
}

output "alb_https_enabled" {
  description = "Whether ACM-backed HTTPS is configured on the ALB"
  value       = module.alb.https_enabled
}

output "waf_web_acl_id" {
  description = "WAF Web ACL ID (empty when WAF is disabled)"
  value       = try(module.waf[0].web_acl_id, "")
}

output "waf_web_acl_arn" {
  description = "WAF Web ACL ARN (empty when WAF is disabled)"
  value       = try(module.waf[0].web_acl_arn, "")
}

output "waf_web_acl_name" {
  description = "WAF Web ACL name (empty when WAF is disabled)"
  value       = try(module.waf[0].web_acl_name, "")
}

output "waf_log_group_name" {
  description = "CloudWatch log group used by WAF (empty when disabled)"
  value       = try(module.waf[0].waf_log_group_name, "")
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.ecs.cluster_name
}

output "ecs_cluster_arn" {
  description = "ECS cluster ARN"
  value       = module.ecs.cluster_arn
}

output "backend_service_name" {
  description = "Backend ECS service name"
  value       = module.ecs.backend_service_name
}

output "frontend_service_name" {
  description = "Frontend ECS service name"
  value       = module.ecs.frontend_service_name
}

output "backend_task_definition_arn" {
  description = "Backend task definition ARN"
  value       = module.ecs.backend_task_definition_arn
}

output "frontend_task_definition_arn" {
  description = "Frontend task definition ARN"
  value       = module.ecs.frontend_task_definition_arn
}

output "application_url" {
  description = "Primary app URL (HTTPS when acm_certificate_arn is set)"
  value       = module.alb.https_enabled ? "https://${module.alb.alb_dns_name}" : "http://${module.alb.alb_dns_name}"
}

output "backend_url" {
  description = "Backend API base URL"
  value       = module.alb.https_enabled ? "https://${module.alb.alb_dns_name}/api" : "http://${module.alb.alb_dns_name}/api"
}

output "frontend_url" {
  description = "Frontend URL"
  value       = module.alb.https_enabled ? "https://${module.alb.alb_dns_name}" : "http://${module.alb.alb_dns_name}"
}

output "sagemaker_endpoint_name" {
  description = "SageMaker unified endpoint name (empty if disabled)"
  value       = try(module.sagemaker_unified[0].endpoint_name, "")
}

output "sagemaker_endpoint_arn" {
  description = "SageMaker unified endpoint ARN (empty if disabled)"
  value       = try(module.sagemaker_unified[0].endpoint_arn, "")
}

output "sagemaker_execution_role_arn" {
  description = "SageMaker execution role ARN (empty if disabled)"
  value       = try(module.sagemaker_unified[0].execution_role_arn, "")
}

output "search_cache_serverless_name" {
  description = "ElastiCache Serverless cache name (empty if disabled)"
  value       = try(aws_elasticache_serverless_cache.search_cache[0].name, "")
}

output "search_cache_endpoint" {
  description = "ElastiCache Serverless endpoint address (empty if disabled)"
  value       = try(aws_elasticache_serverless_cache.search_cache[0].endpoint[0].address, "")
}

output "search_cache_port" {
  description = "ElastiCache Serverless endpoint port (0 if disabled)"
  value       = try(aws_elasticache_serverless_cache.search_cache[0].endpoint[0].port, 0)
}

output "search_cache_security_group_id" {
  description = "Security group ID attached to ElastiCache Serverless cache (empty if disabled)"
  value       = try(aws_security_group.search_cache[0].id, "")
}

output "backend_search_cache_redis_url" {
  description = "SEARCH_CACHE_REDIS_URL value injected into ECS backend task"
  value       = local.search_cache_redis_url
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "default_vpc_id" {
  description = "Default VPC ID"
  value       = data.aws_vpc.default.id
}

output "aws_account_id" {
  description = "AWS account ID"
  value       = data.aws_caller_identity.current.account_id
}
