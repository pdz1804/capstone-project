# Quick Start: Deploy LibreOffice Lambda Container

## 🚀 5-Minute Deployment

### Prerequisites Check

```bash
# 1. Check Docker is running
docker ps

# 2. Check AWS CLI is configured
aws sts get-caller-identity

# 3. Navigate to directory
cd Phase_2_FE_AI_Merge/scripts/lambda_office_converter
```

### Deploy Now!

**For Windows (PowerShell):**
```powershell
.\deploy-container.ps1
```

**For Linux/Mac (Bash):**
```bash
chmod +x deploy-container.sh
./deploy-container.sh
```

That's it! The script will:
- ✅ Build Docker image (877 MB)
- ✅ Create ECR repository
- ✅ Push image to AWS
- ✅ Deploy Lambda function
- ✅ Run test conversion

**Time**: ~5-10 minutes first time, ~2 minutes for updates

---

## What Just Happened?

### 1. Docker Image Built

Uses **public.ecr.aws/shelf/lambda-libreoffice-base:26.2-python3.12-x86_64**:
- LibreOffice 26.2.2 (latest!)
- Python 3.12 runtime
- CJK fonts included
- 877 MB total

### 2. Lambda Created

- **Name**: `office-to-pdf-converter`
- **Memory**: 3008 MB
- **Timeout**: 180 seconds
- **Type**: Container Image

### 3. Test Ran

Converted HTML → PDF successfully!

Check the output file: `test-output.pdf`

---

## Next Steps

### 1. Configure Backend

Add to your `.env`:

```bash
OFFICE_PDF_LAMBDA_FUNCTION_NAME=office-to-pdf-converter
OFFICE_PDF_LAMBDA_REGION=us-west-2
OFFICE_PDF_CONVERTER_MODE=auto
```

### 2. Grant ECS Permission

```bash
# Find your ECS task role name
aws ecs describe-task-definition \
  --task-definition your-task-definition \
  --query 'taskDefinition.taskRoleArn' \
  --output text

# Grant permission (replace role name)
aws iam put-role-policy \
  --role-name YOUR-ECS-TASK-ROLE-NAME \
  --policy-name LambdaOfficeConverter \
  --policy-document file://ecs-lambda-invoke-policy.json
```

### 3. Test Integration

```bash
# Upload a DOCX file through your backend API
# Check logs for:
# "→ Trying AWS Lambda LibreOffice conversion..."
# "✓ AWS Lambda conversion successful"
```

---

## Test Manually

```bash
# Test with DOCX
echo '<docx-content-base64>' | base64 -d > test.docx

aws lambda invoke \
  --function-name office-to-pdf-converter \
  --payload '{"operation":"convert-to-pdf","filename":"test.docx","extension":".docx","content_base64":"<your-base64>"}' \
  --region us-west-2 \
  output.json

cat output.json
```

---

## Update Lambda

When LibreOffice base image updates:

```bash
# Pull latest
docker pull public.ecr.aws/shelf/lambda-libreoffice-base:26.2-python3.12-x86_64

# Redeploy
./deploy-container.sh  # or .ps1
```

---

## Common Issues

### ❌ "Docker not running"

**Solution**: Start Docker Desktop (Windows/Mac) or `sudo systemctl start docker` (Linux)

### ❌ "aws command not found"

**Solution**: Install AWS CLI - https://aws.amazon.com/cli/

### ❌ "Access denied to ECR"

**Solution**: 
```bash
aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin \
  $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-west-2.amazonaws.com
```

### ❌ "Lambda timeout"

**Solution**: Increase timeout
```bash
aws lambda update-function-configuration \
  --function-name office-to-pdf-converter \
  --timeout 300
```

---

## Cost

**Monthly estimate for 1000 conversions**:
- Lambda compute: ~$0.25
- ECR storage: ~$0.09
- **Total: ~$0.34/month**

Free tier: First 1M requests + 400,000 GB-seconds free!

---

## Architecture

```
Your Backend (ECS)
      ↓
   invoke
      ↓
AWS Lambda Container
 (LibreOffice 26.2)
      ↓
  Convert
      ↓
   PDF (base64)
      ↓
   return
```

---

## 🎯 Success Checklist

- [ ] Docker is running
- [ ] AWS CLI configured
- [ ] Deployment script ran successfully
- [ ] Test PDF created
- [ ] Backend `.env` updated
- [ ] ECS task role has permission
- [ ] Test file uploaded through API

---

## 🆘 Need Help?

- **Logs**: `aws logs tail /aws/lambda/office-to-pdf-converter --follow`
- **Function info**: `aws lambda get-function --function-name office-to-pdf-converter`
- **Test locally**: `docker run -it --rm -v $(pwd):/work public.ecr.aws/shelf/lambda-libreoffice-base:26.2-python3.12-x86_64 bash`

---

## 📚 More Info

- [Full README](README.md)
- [Shelf.io Base Image](https://github.com/shelfio/libreoffice-lambda-base-image)
- [Backend Integration](../../backend/src/processor/normalizer.py#L457)

---

**Congrats! Your LibreOffice Lambda is deployed! 🎉**
