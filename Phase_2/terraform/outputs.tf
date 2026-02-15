# ===================== ECR Outputs =====================
output "backend_ecr_repository_url" {
  description = "Backend ECR repository URL"
  value       = module.backend_ecr.repository_url
}

output "frontend_ecr_repository_url" {
  description = "Frontend ECR repository URL"
  value       = module.frontend_ecr.repository_url
}

output "backend_ecr_registry_id" {
  description = "Backend ECR registry ID"
  value       = module.backend_ecr.registry_id
}

# ===================== ALB Outputs =====================
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

# ===================== ECS Outputs =====================
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

# ===================== Access Information =====================
output "application_url" {
  description = "Application URL"
  value       = "http://${module.alb.alb_dns_name}"
}

output "backend_url" {
  description = "Backend API URL"
  value       = "http://${module.alb.alb_dns_name}/api"
}

output "frontend_url" {
  description = "Frontend URL"
  value       = "http://${module.alb.alb_dns_name}"
}

# ===================== AWS Account Info =====================
output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "default_vpc_id" {
  description = "Default VPC ID"
  value       = data.aws_vpc.default.id
}
