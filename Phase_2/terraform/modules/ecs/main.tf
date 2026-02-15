# ECS Module - Cluster and Services

variable "cluster_name" {
  description = "Name of the ECS cluster"
  type        = string
}

variable "backend_config" {
  description = "Backend service configuration"
  type = object({
    name                   = string
    image_uri              = string
    port                   = number
    cpu                    = number
    memory                 = number
    desired_count          = number
    min_capacity           = number
    max_capacity           = number
    container_name         = string
  })
}

variable "frontend_config" {
  description = "Frontend service configuration"
  type = object({
    name                   = string
    image_uri              = string
    port                   = number
    cpu                    = number
    memory                 = number
    desired_count          = number
    min_capacity           = number
    max_capacity           = number
    container_name         = string
  })
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for ECS tasks"
  type        = list(string)
}

variable "alb_security_group_id" {
  description = "Security group ID of the ALB"
  type        = string
}

variable "backend_target_group_arn" {
  description = "Backend target group ARN"
  type        = string
}

variable "frontend_target_group_arn" {
  description = "Frontend target group ARN"
  type        = string
}

variable "ecs_task_execution_role_arn" {
  description = "ECS task execution role ARN"
  type        = string
}

variable "ecs_task_role_arn" {
  description = "ECS task role ARN"
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7
}

variable "tags" {
  description = "Tags for ECS resources"
  type        = map(string)
  default     = {}
}

variable "frontend_task_execution_role_arn" {
  description = "Frontend ECS task execution role ARN"
  type        = string
  default     = ""
}

variable "frontend_task_role_arn" {
  description = "Frontend ECS task role ARN"
  type        = string
  default     = ""
}

# Security group for ECS tasks
resource "aws_security_group" "ecs_tasks" {
  name        = "${var.cluster_name}-ecs-tasks-sg"
  description = "Security group for ECS tasks"
  vpc_id      = var.vpc_id

  # Ingress from ALB
  ingress {
    from_port       = 0
    to_port         = 65535
    protocol        = "tcp"
    security_groups = [var.alb_security_group_id]
    description     = "Allow traffic from ALB"
  }

  # Inter-task communication
  ingress {
    from_port = 0
    to_port   = 65535
    protocol  = "tcp"
    self      = true
    description = "Allow inter-task communication"
  }

  # Egress - allow all
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-ecs-tasks-sg"
  })
}

# ECS Cluster with Container Insights
resource "aws_ecs_cluster" "main" {
  name = var.cluster_name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = merge(var.tags, {
    Name = var.cluster_name
  })
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${var.cluster_name}/backend"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name = "ecs-backend-logs"
  })
}

resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/ecs/${var.cluster_name}/frontend"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name = "ecs-frontend-logs"
  })
}

# Backend Task Definition
resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.cluster_name}-backend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.backend_config.cpu
  memory                   = var.backend_config.memory

  execution_role_arn = var.ecs_task_execution_role_arn
  task_role_arn      = var.ecs_task_role_arn

  container_definitions = jsonencode([
    {
      name      = var.backend_config.container_name
      image     = var.backend_config.image_uri
      essential = true
      portMappings = [
        {
          containerPort = var.backend_config.port
          hostPort      = var.backend_config.port
          protocol      = "tcp"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.backend.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "ecs"
        }
      }
      environment = [
        {
          name  = "LOG_LEVEL"
          value = "INFO"
        },
        {
          name  = "ENVIRONMENT"
          value = "production"
        }
      ]
      # Health check
      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:${var.backend_config.port}/health')\" || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-backend-task"
  })

  depends_on = [
    aws_cloudwatch_log_group.backend
  ]
}

# Frontend Task Definition
resource "aws_ecs_task_definition" "frontend" {
  family                   = "${var.cluster_name}-frontend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.frontend_config.cpu
  memory                   = var.frontend_config.memory

  execution_role_arn = var.frontend_task_execution_role_arn != "" ? var.frontend_task_execution_role_arn : var.ecs_task_execution_role_arn
  task_role_arn      = var.frontend_task_role_arn != "" ? var.frontend_task_role_arn : var.ecs_task_role_arn

  container_definitions = jsonencode([
    {
      name      = var.frontend_config.container_name
      image     = var.frontend_config.image_uri
      essential = true
      portMappings = [
        {
          containerPort = var.frontend_config.port
          hostPort      = var.frontend_config.port
          protocol      = "tcp"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.frontend.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "ecs"
        }
      }
      environment = [
        {
          name  = "LOG_LEVEL"
          value = "INFO"
        }
      ]
      # Health check
      healthCheck = {
        command     = ["CMD-SHELL", "wget --quiet --tries=1 --spider http://localhost:${var.frontend_config.port}/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 10
      }
    }
  ])

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-frontend-task"
  })

  depends_on = [
    aws_cloudwatch_log_group.frontend
  ]
}

# Backend Service
resource "aws_ecs_service" "backend" {
  name            = "${var.cluster_name}-backend-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.backend_config.desired_count
  launch_type     = "FARGATE"

  force_new_deployment = true

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = var.backend_target_group_arn
    container_name   = var.backend_config.container_name
    container_port   = var.backend_config.port
  }

  depends_on = [
    aws_ecs_task_definition.backend
  ]

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-backend-service"
  })
}

# Frontend Service
resource "aws_ecs_service" "frontend" {
  name            = "${var.cluster_name}-frontend-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = var.frontend_config.desired_count
  launch_type     = "FARGATE"

  force_new_deployment = true

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = var.frontend_target_group_arn
    container_name   = var.frontend_config.container_name
    container_port   = var.frontend_config.port
  }

  depends_on = [
    aws_ecs_task_definition.frontend
  ]

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-frontend-service"
  })
}

# Get current region for logging
data "aws_region" "current" {}

output "cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "cluster_arn" {
  description = "ECS cluster ARN"
  value       = aws_ecs_cluster.main.arn
}

output "backend_service_name" {
  description = "Backend service name"
  value       = aws_ecs_service.backend.name
}

output "frontend_service_name" {
  description = "Frontend service name"
  value       = aws_ecs_service.frontend.name
}

output "backend_task_definition_arn" {
  description = "Backend task definition ARN"
  value       = aws_ecs_task_definition.backend.arn
}

output "frontend_task_definition_arn" {
  description = "Frontend task definition ARN"
  value       = aws_ecs_task_definition.frontend.arn
}

output "ecs_tasks_security_group_id" {
  description = "Security group ID for ECS tasks"
  value       = aws_security_group.ecs_tasks.id
}


