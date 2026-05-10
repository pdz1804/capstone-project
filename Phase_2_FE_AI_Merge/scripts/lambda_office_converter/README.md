# Office to PDF Lambda Converter

**Modern container-based Lambda** using **LibreOffice 26.2** (updated April 2026!)

Converts office files (DOCX, PPTX, XLSX, HTML, etc.) to PDF using LibreOffice in AWS Lambda.

## ✨ What's New

- ✅ **LibreOffice 26.2.2** - Latest version (April 14, 2026)
- ✅ **Container-based** - Using Lambda Container Images (not layers)
- ✅ **877 MB image** - Pre-built by [Shelf.io](https://github.com/shelfio/libreoffice-lambda-base-image)
- ✅ **CJK fonts** - Full Asian language support
- ✅ **Python 3.12** - Modern runtime

## Prerequisites

1. **Docker** installed and running
   ```bash
   docker --version
   ```

2. **AWS CLI** installed and configured
   ```bash
   aws configure
   ```

3. **AWS Account** with permissions to:
   - Create Lambda functions
   - Create/push to ECR repositories
   - Create IAM roles

## 🚀 Quick Start

### Option 1: Using Bash (Linux/Mac/WSL)

```bash
cd Phase_2_FE_AI_Merge/scripts/lambda_office_converter
chmod +x deploy-container.sh
./deploy-container.sh
```

### Option 2: Using PowerShell (Windows)

```powershell
cd Phase_2_FE_AI_Merge\scripts\lambda_office_converter
.\deploy-container.ps1
```

## What the Script Does

1. **Creates ECR repository** - Private Docker registry
2. **Builds Docker image** - Uses Shelf.io LibreOffice base image
3. **Pushes to ECR** - Uploads container to AWS
4. **Creates Lambda function** - Deploys as container
5. **Tests conversion** - HTML → PDF test

**Total time**: ~5-10 minutes (first time)

## Configuration

### Backend Environment Variables

Add to your `.env` file or ECS task definition:

```bash
# Lambda converter settings
OFFICE_PDF_LAMBDA_FUNCTION_NAME=office-to-pdf-converter
OFFICE_PDF_LAMBDA_REGION=us-west-2

# Converter mode: "auto", "local", or "lambda"
OFFICE_PDF_CONVERTER_MODE=auto
```

### IAM Permissions for ECS Task Role

Your ECS task role needs permission to invoke Lambda:

```bash
aws iam put-role-policy \
  --role-name <your-ecs-task-role> \
  --policy-name InvokeLambda \
  --policy-document file://ecs-lambda-invoke-policy.json
```

## Testing

### Test the Lambda directly:

```bash
# Create test payload
echo '{
  "operation": "convert-to-pdf",
  "filename": "test.html",
  "extension": ".html",
  "content_base64": "PGh0bWw+PGJvZHk+PGgxPkhlbGxvPC9oMT48L2JvZHk+PC9odG1sPg=="
}' > test.json

# Invoke Lambda
aws lambda invoke \
  --function-name office-to-pdf-converter \
  --payload file://test.json \
  --region us-west-2 \
  response.json

# Check result
cat response.json
```

### Test from backend:

Your backend ([normalizer.py:457](../../backend/src/processor/normalizer.py#L457)) will automatically use Lambda when:
- Running in ECS/cloud environment
- `FILE_STORAGE_BACKEND=s3` is set
- Environment variables are configured

## Architecture

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  Backend    │         │   Lambda     │         │   Docker    │
│   (ECS)     │────────▶│  Container   │────────▶│ LibreOffice │
│             │ invoke  │              │         │    26.2     │
└─────────────┘         └──────────────┘         └─────────────┘
     │                          │
     │                          │
     │                          ▼
     │                  ┌──────────────┐
     │                  │ Convert to   │
     │                  │     PDF      │
     │                  └──────────────┘
     │                          │
     │◀─────────────────────────┘
     │    PDF (base64)
```

## Files

- **Dockerfile** - Container definition using Shelf.io base image
- **handler.py** - Lambda handler (Python 3.12)
- **deploy-container.sh** - Bash deployment script
- **deploy-container.ps1** - PowerShell deployment script
- **ecs-lambda-invoke-policy.json** - IAM policy for ECS
- **README.md** - This file

## Cost Estimation

Lambda Container pricing:
- **Compute**: ~$0.0000166667 per GB-second
- **Storage**: $0.10 per GB-month (ECR)
- **Requests**: $0.20 per 1M requests

**Example**:
- 1000 conversions/month
- Average 5 seconds per conversion
- 3 GB memory
- Cost: ~$0.25/month + $0.09 storage = **~$0.34/month**

Still much cheaper than running LibreOffice 24/7 in ECS!

## Related Maintained Docs

- [`../../README.md`](../../README.md)   maintained merged application overview.
- [`../../../docs/technical/APPLICATION_OVERVIEW.md`](../../../docs/technical/APPLICATION_OVERVIEW.md)   system capabilities and architecture summary.
- [`../../../docs/technical/API_REFERENCE.md`](../../../docs/technical/API_REFERENCE.md)   API map and operational guidance.
- [`../../../docs/testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md`](../../../docs/testing/FINAL_APPLICATION_PERFORMANCE_REPORT_20260426.md)   performance evidence and scaling plan.

## Supported Formats

### Input Formats:
- **Documents**: DOCX, DOC, ODT, RTF
- **Presentations**: PPTX, PPT, ODP
- **Spreadsheets**: XLSX, XLS, CSV
- **Web**: HTML, MHTML
- **Images**: PNG, JPG, TIFF

### Output Format:
- PDF (high quality, preserves formatting)

## Troubleshooting

### Docker not running

```bash
# Start Docker
# Windows: Open Docker Desktop
# Linux: sudo systemctl start docker
# Mac: Open Docker app
```

### ECR push fails

```bash
# Re-login to ECR
aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin \
  <account-id>.dkr.ecr.us-west-2.amazonaws.com
```

### Lambda timeout

```bash
# Increase timeout to 5 minutes
aws lambda update-function-configuration \
  --function-name office-to-pdf-converter \
  --timeout 300 \
  --memory-size 3008
```

### View logs

```bash
aws logs tail /aws/lambda/office-to-pdf-converter --follow
```

## Updating

To update to a new version:

```bash
# Pull latest base image
docker pull public.ecr.aws/shelf/lambda-libreoffice-base:26.2-python3.12-x86_64

# Redeploy
./deploy-container.sh  # or deploy-container.ps1
```

## References

- [LibreOffice Lambda Base Image](https://github.com/shelfio/libreoffice-lambda-base-image) - Maintained base images
- [Serverless LibreOffice](https://github.com/vladgolubev/serverless-libreoffice) - Original project
- [AWS Lambda Containers](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html) - Container documentation

---

**Ready to deploy? Run `./deploy-container.sh` (Linux/Mac) or `.\deploy-container.ps1` (Windows)**
