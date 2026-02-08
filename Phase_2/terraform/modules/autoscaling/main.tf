# Auto-scaling Module - ECS Service auto-scaling

variable "service_arn" {
  description = "ARN of the ECS service"
  type        = string
}

variable "cluster_name" {
  description = "Name of the ECS cluster"
  type        = string
}

variable "service_name" {
  description = "Name of the ECS service"
  type        = string
}

variable "min_capacity" {
  description = "Minimum number of tasks"
  type        = number
  default     = 1
}

variable "max_capacity" {
  description = "Maximum number of tasks"
  type        = number
  default     = 10
}

variable "cpu_target_tracking_desired_value" {
  description = "Target CPU utilization percentage"
  type        = number
  default     = 70
}

variable "memory_target_tracking_desired_value" {
  description = "Target memory utilization percentage"
  type        = number
  default     = 80
}

variable "scale_out_cooldown" {
  description = "Scale out cooldown in seconds"
  type        = number
  default     = 60
}

variable "scale_in_cooldown" {
  description = "Scale in cooldown in seconds"
  type        = number
  default     = 300
}

variable "tags" {
  description = "Tags for auto-scaling resources"
  type        = map(string)
  default     = {}
}

# Auto-scaling target
resource "aws_appautoscaling_target" "ecs_target" {
  max_capacity       = var.max_capacity
  min_capacity       = var.min_capacity
  resource_id        = "service/${var.cluster_name}/${var.service_name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

# CPU-based scaling policy
resource "aws_appautoscaling_policy" "ecs_policy_cpu" {
  name               = "${var.service_name}-cpu-autoscaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs_target.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs_target.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = var.cpu_target_tracking_desired_value
    scale_out_cooldown = var.scale_out_cooldown
    scale_in_cooldown  = var.scale_in_cooldown
  }

  depends_on = [aws_appautoscaling_target.ecs_target]
}

# Memory-based scaling policy
resource "aws_appautoscaling_policy" "ecs_policy_memory" {
  name               = "${var.service_name}-memory-autoscaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs_target.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs_target.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageMemoryUtilization"
    }
    target_value       = var.memory_target_tracking_desired_value
    scale_out_cooldown = var.scale_out_cooldown
    scale_in_cooldown  = var.scale_in_cooldown
  }

  depends_on = [aws_appautoscaling_target.ecs_target]
}

# ALB request count-based scaling (optional)
resource "aws_appautoscaling_policy" "ecs_policy_alb_request_count" {
  name               = "${var.service_name}-alb-request-count-autoscaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs_target.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs_target.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ALBRequestCountPerTarget"
    }
    target_value = 1000
  }

  depends_on = [aws_appautoscaling_target.ecs_target]
}

output "autoscaling_target_id" {
  description = "Auto-scaling target ID"
  value       = aws_appautoscaling_target.ecs_target.id
}

output "cpu_scaling_policy_arn" {
  description = "CPU scaling policy ARN"
  value       = aws_appautoscaling_policy.ecs_policy_cpu.arn
}

output "memory_scaling_policy_arn" {
  description = "Memory scaling policy ARN"
  value       = aws_appautoscaling_policy.ecs_policy_memory.arn
}
