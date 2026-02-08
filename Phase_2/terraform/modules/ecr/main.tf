# ECR Module - Create repositories for Docker images

variable "repository_name" {
  description = "Name of the ECR repository"
  type        = string
}

variable "image_tag_mutability" {
  description = "The tag mutability setting for the repository"
  type        = string
  default     = "MUTABLE"
}

variable "scan_on_push" {
  description = "Indicate whether images are scanned after being pushed to the repository"
  type        = bool
  default     = true
}

variable "image_retention_count" {
  description = "Number of images to keep in the repository"
  type        = number
  default     = 10
}

variable "tags" {
  description = "Tags to apply to the repository"
  type        = map(string)
  default     = {}
}

# Create ECR repository
resource "aws_ecr_repository" "main" {
  name                 = var.repository_name
  image_tag_mutability = var.image_tag_mutability

  image_scanning_configuration {
    scan_on_push = var.scan_on_push
  }

  tags = var.tags

  depends_on = []
}

# Set lifecycle policy to keep only the latest N images
resource "aws_ecr_lifecycle_policy" "main" {
  repository = aws_ecr_repository.main.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last ${var.image_retention_count} images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v"]
          countType     = "imageCountMoreThan"
          countNumber   = var.image_retention_count
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Expire untagged images after 30 days"
        selection = {
          tagStatus       = "untagged"
          countType       = "sinceImagePushed"
          countUnit       = "days"
          countNumber     = 30
        }
        action = {
          type = "expire"
        }
      }
    ]
  })

  depends_on = [aws_ecr_repository.main]
}

output "repository_url" {
  description = "The URL of the ECR repository"
  value       = aws_ecr_repository.main.repository_url
}

output "repository_arn" {
  description = "The ARN of the ECR repository"
  value       = aws_ecr_repository.main.arn
}

output "registry_id" {
  description = "The registry ID"
  value       = aws_ecr_repository.main.registry_id
}
