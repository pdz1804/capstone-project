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
