# Terraform Infrastructure for RAG Pipeline

Complete Infrastructure as Code for deploying RAG Pipeline to AWS ECS.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Internet                                  │
└────────────────────────────┬────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   ALB (ELB)     │
                    │   Port 80       │
                    └────────┬────────┘
                             │
             ┌───────────────┼───────────────┐
             │               │               │
         ┌───▼────────┐ ┌───▼────────┐     │
         │  Frontend  │ │  Backend   │     │
         │   Tasks    │ │   Tasks    │     │
         │  (Port 80) │ │ (Port 8000)│     │
         └───────────┘ └────────────┘     │
             │               │             │
             └───────────────┼─────────────┘
                             │
                    ┌────────▼─────────┐
                    │  ECS Cluster     │
                    │  (Fargate)       │
                    └──────────────────┘
                             │
             ┌───────────────┼───────────────┐
             │               │               │
        ┌────▼─────┐   ┌────▼─────┐         │
        │ Backend  │   │ Frontend  │         │
        │   ECR    │   │   ECR     │         │
        └──────────┘   └───────────┘         │
             │               │               │
     ┌──────▼──────┐  ┌─────▼──────┐  ┌────▼────┐
     │ CloudWatch  │  │ CloudWatch │  │ VPC     │
     │ Logs (BE)   │  │ Logs (FE)  │  │ Default │
     └─────────────┘  └────────────┘  └─────────┘
```

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **Terraform** >= 1.0 installed
3. **AWS CLI v2** configured with credentials
4. **Docker** for building images
5. **Docker images** pushed to ECR repositories

### Install prerequisites (Windows)

Use `winget` (recommended):

```powershell
winget install --id Hashicorp.Terraform -e
winget install --id Amazon.AWSCLI -e
```

If `winget` is unavailable, install manually:

- Terraform: https://developer.hashicorp.com/terraform/downloads
- AWS CLI v2 (Windows x86_64): https://awscli.amazonaws.com/AWSCLIV2.msi

Verify installation:

```powershell
terraform version
aws --version
```

Configure AWS credentials (interactive):

```powershell
aws configure
aws sts get-caller-identity
```

## Project Structure

```
terraform/
├── main.tf                          # Main configuration
├── variables.tf                     # Input variables
├── outputs.tf                       # Output values
├── terraform.tfvars.example         # Example variables
├── README.md                        # This file
├── modules/
│   ├── ecr/
│   │   └── main.tf                 # ECR repository module
│   ├── iam/
│   │   └── main.tf                 # IAM roles module
│   ├── alb/
│   │   └── main.tf                 # Load balancer module
│   ├── ecs/
│   │   └── main.tf                 # ECS cluster & services module
│   └── autoscaling/
│       └── main.tf                 # Auto-scaling module
└── .gitignore                       # Git ignore patterns
```

## 📋 Setup Steps

### 1. Initialize Terraform

```bash
cd Phase_2/terraform

# Initialize Terraform
terraform init

echo "✅ Terraform initialized"
```

### 2. Configure Variables

```bash
# Copy example variables to terraform.tfvars
# Linux/macOS
cp terraform.tfvars.example terraform.tfvars

# Windows PowerShell
Copy-Item terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your configuration
# vim terraform.tfvars
```

### 3. Plan Infrastructure

```bash
# Review infrastructure changes
terraform plan -out=tfplan

echo "📋 Plan saved to tfplan"
```

### 4. Apply Infrastructure

```bash
# Apply the infrastructure
terraform apply tfplan

echo "✅ Infrastructure deployed successfully"
```

### 5. Deploy Docker Images

```bash
# Build and push backend image
cd ../backend
docker build -t rag-pipeline-backend:latest .
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-west-2.amazonaws.com
docker tag rag-pipeline-backend:latest <ACCOUNT_ID>.dkr.ecr.us-west-2.amazonaws.com/rag-pipeline-backend:latest
docker push <ACCOUNT_ID>.dkr.ecr.us-west-2.amazonaws.com/rag-pipeline-backend:latest

# Build and push frontend image
cd ../frontend
docker build -t rag-pipeline-frontend:latest .
docker tag rag-pipeline-frontend:latest <ACCOUNT_ID>.dkr.ecr.us-west-2.amazonaws.com/rag-pipeline-frontend:latest
docker push <ACCOUNT_ID>.dkr.ecr.us-west-2.amazonaws.com/rag-pipeline-frontend:latest

echo "✅ Docker images deployed to ECR"
```

## 🔧 Configuration

### Backend Service
- **CPU**: 512 units (0.5 vCPU)
- **Memory**: 1024 MB (1 GB)
- **Port**: 8000
- **Desired Count**: 2
- **Min/Max Scaling**: 1-10 tasks

### Frontend Service
- **CPU**: 256 units (0.25 vCPU)
- **Memory**: 512 MB
- **Port**: 80
- **Desired Count**: 2
- **Min/Max Scaling**: 1-5 tasks

### Auto-Scaling Policies
- **CPU Target**: 70%
- **Memory Target**: 80%
- **Scale-out Cooldown**: 60 seconds
- **Scale-in Cooldown**: 300 seconds

## 📊 Outputs

After applying Terraform, you'll get:

```
alb_dns_name          = "rag-pipeline-alb-1234567.us-west-2.elb.amazonaws.com"
application_url       = "http://rag-pipeline-alb-1234567.us-west-2.elb.amazonaws.com"
backend_ecr_repository_url = "123456789.dkr.ecr.us-west-2.amazonaws.com/rag-pipeline-backend"
backend_service_name  = "rag-pipeline-cluster-backend-service"
ecs_cluster_name      = "rag-pipeline-cluster"
frontend_ecr_repository_url = "123456789.dkr.ecr.us-west-2.amazonaws.com/rag-pipeline-frontend"
frontend_service_name = "rag-pipeline-cluster-frontend-service"
```

## 🔄 Updating Infrastructure

### Update Desired Count

```bash
terraform apply -var="backend_desired_count=3" -var="frontend_desired_count=3"
```

### Update Auto-Scaling Limits

```bash
terraform apply \
  -var="backend_max_capacity=20" \
  -var="frontend_max_capacity=10"
```

### Update Scaling Targets

```bash
terraform apply \
  -var="backend_cpu_target=80" \
  -var="backend_memory_target=85"
```

## 🧹 Cleanup

```bash
# Destroy all infrastructure
terraform destroy

# Or destroy with variables
terraform destroy \
  -var="backend_desired_count=2" \
  -var="frontend_desired_count=2"

echo "✅ Infrastructure destroyed"
```

## 🔐 Security Considerations

1. **VPC**: Uses default VPC for simplicity (change for production)
2. **Subnets**: Spreads across availability zones
3. **Security Groups**: 
   - ALB accepts HTTP/HTTPS from anywhere
   - ECS tasks accept traffic only from ALB
4. **IAM Roles**: Minimal permissions for ECS tasks
5. **ECR**: Image scanning enabled, lifecycle policy keeps latest 10 images
6. **Logs**: CloudWatch logs with 7-day retention

### Recommendations for Production

```hcl
# 1. Enable S3 backend for state management
# 2. Enable VPC encryption
# 3. Use private subnets with NAT Gateway
# 4. Enable WAF on ALB
# 5. Use ACM certificate for HTTPS
# 6. Enable HTTPS listener with redirect from HTTP
# 7. Use RDS/ElastiCache in private subnets
# 8. Enable VPC Flow Logs
# 9. Enable GuardDuty for threat detection
# 10. Use Systems Manager Session Manager instead of SSH
```

## 🐛 Troubleshooting

### Error: "Unable to assume role"

```bash
# Check IAM role policy
aws iam get-role-policy --role-name <ROLE_NAME> --policy-name <POLICY_NAME>
```

### Error: "Image not found"

```bash
# Check ECR repository
aws ecr describe-repositories

# Check image uploads
aws ecr list-images --repository-name <REPO_NAME>
```

### Error: "Task stopped"

```bash
# Check ECS task status
aws ecs describe-tasks \
  --cluster <CLUSTER_NAME> \
  --tasks <TASK_ARN>

# Check task logs
aws logs tail /ecs/<CLUSTER_NAME>/backend --follow
```

### Error: "Health check failed"

```bash
# Check service events
aws ecs describe-services \
  --cluster <CLUSTER_NAME> \
  --services <SERVICE_NAME> \
  --query services[0].events

# Check target group health
aws elbv2 describe-target-health \
  --target-group-arn <TARGET_GROUP_ARN>
```

## 📈 Monitoring

### CloudWatch Logs

```bash
# View backend logs
aws logs tail /ecs/<CLUSTER_NAME>/backend --follow

# View frontend logs
aws logs tail /ecs/<CLUSTER_NAME>/frontend --follow
```

### Container Insights

Access Container Insights dashboard in CloudWatch console:
- ECS cluster metrics
- Service metrics
- Task metrics
- Network metrics

### ECS Dashboard

```bash
# Get service status
aws ecs describe-services \
  --cluster <CLUSTER_NAME> \
  --services <SERVICE_NAME>

# Get task count
aws ecs describe-services \
  --cluster <CLUSTER_NAME> \
  --services <SERVICE_NAME> \
  --query services[0].{
    Running: runningCount,
    Desired: desiredCount,
    Pending: pendingCount
  }
```

## 📚 Documentation

For more information:
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [AWS ECR Documentation](https://docs.aws.amazon.com/ecr/)
- [AWS ALB Documentation](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/)

## 🤝 Support

For issues or questions:
1. Check Terraform logs: `terraform debug`
2. Check AWS CloudTrail for API calls
3. Review CloudWatch Logs for application errors
4. Check ECS task events for deployment issues

## ✅ Deployment Checklist

- [ ] AWS credentials configured
- [ ] Terraform initialized
- [ ] Variables reviewed and updated
- [ ] Plan reviewed
- [ ] Infrastructure applied
- [ ] Docker images built
- [ ] Images pushed to ECR
- [ ] Application accessible via ALB DNS
- [ ] Health checks passing
- [ ] Auto-scaling working
- [ ] CloudWatch logs visible
- [ ] Monitoring configured

---

**Last Updated:** February 8, 2026  
**Terraform Version:** >= 1.0  
**AWS Provider Version:** ~> 5.25
