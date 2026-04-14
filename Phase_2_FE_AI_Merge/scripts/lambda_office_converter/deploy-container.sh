#!/bin/bash
# Deploy LibreOffice Lambda Container Function

set -e

# Configuration
FUNCTION_NAME="office-to-pdf-converter"
REGION="${AWS_REGION:-us-west-2}"
MEMORY=3008
TIMEOUT=180

# Get AWS Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${FUNCTION_NAME}"

echo "========================================"
echo "Deploying LibreOffice Lambda Container"
echo "========================================"
echo "Function: $FUNCTION_NAME"
echo "Region: $REGION"
echo "Account: $ACCOUNT_ID"
echo ""

# Step 1: Create ECR repository if it doesn't exist
echo "Step 1: Creating ECR repository..."
if ! aws ecr describe-repositories --repository-names $FUNCTION_NAME --region $REGION 2>/dev/null; then
    echo "Creating repository..."
    aws ecr create-repository \
        --repository-name $FUNCTION_NAME \
        --region $REGION
    echo "✓ Repository created"
else
    echo "✓ Repository already exists"
fi

# Step 2: Login to ECR
echo ""
echo "Step 2: Logging into ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com
echo "✓ Logged in"

# Step 3: Build Docker image
echo ""
echo "Step 3: Building Docker image..."
docker build -t $FUNCTION_NAME:latest .
echo "✓ Image built"

# Step 4: Tag and push image
echo ""
echo "Step 4: Pushing image to ECR..."
docker tag $FUNCTION_NAME:latest $ECR_REPO:latest
docker push $ECR_REPO:latest
echo "✓ Image pushed"

# Step 5: Create or update Lambda function
echo ""
echo "Step 5: Creating/updating Lambda function..."

# Check if function exists
if aws lambda get-function --function-name $FUNCTION_NAME --region $REGION 2>/dev/null; then
    echo "Function exists. Updating..."
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --image-uri $ECR_REPO:latest \
        --region $REGION

    echo "Waiting for update to complete..."
    aws lambda wait function-updated \
        --function-name $FUNCTION_NAME \
        --region $REGION

    echo "Updating configuration..."
    aws lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --timeout $TIMEOUT \
        --memory-size $MEMORY \
        --environment Variables={HOME=/tmp} \
        --region $REGION

    echo "✓ Function updated"
else
    echo "Function does not exist. Creating..."

    # Get or create IAM role
    ROLE_NAME="${FUNCTION_NAME}-role"
    ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text 2>/dev/null || echo "")

    if [ -z "$ROLE_ARN" ]; then
        echo "Creating IAM role..."

        # Create trust policy
        cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

        aws iam create-role \
            --role-name $ROLE_NAME \
            --assume-role-policy-document file://trust-policy.json \
            --region $REGION

        # Attach basic execution policy
        aws iam attach-role-policy \
            --role-name $ROLE_NAME \
            --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
            --region $REGION

        rm trust-policy.json

        # Get role ARN
        ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text)

        echo "✓ IAM role created: $ROLE_ARN"
        echo "Waiting 10 seconds for IAM role to propagate..."
        sleep 10
    fi

    # Create Lambda function
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --package-type Image \
        --code ImageUri=$ECR_REPO:latest \
        --role $ROLE_ARN \
        --timeout $TIMEOUT \
        --memory-size $MEMORY \
        --environment Variables={HOME=/tmp} \
        --region $REGION

    echo "✓ Function created"
fi

# Step 6: Test the function
echo ""
echo "Step 6: Testing function..."

# Create test HTML file
TEST_HTML='<html><body><h1>Hello LibreOffice!</h1><p>This is a test document.</p></body></html>'
TEST_BASE64=$(echo -n "$TEST_HTML" | base64)

# Create test payload
cat > test-payload.json <<EOF
{
    "operation": "convert-to-pdf",
    "filename": "test.html",
    "extension": ".html",
    "content_base64": "$TEST_BASE64"
}
EOF

echo "Invoking function..."
aws lambda invoke \
    --function-name $FUNCTION_NAME \
    --payload file://test-payload.json \
    --region $REGION \
    response.json

echo ""
echo "Response:"
cat response.json | python3 -m json.tool

# Check if conversion was successful
if grep -q '"ok": true' response.json; then
    echo ""
    echo "✓ Test conversion successful!"

    # Optionally decode and save PDF
    python3 -c "
import json
import base64
with open('response.json') as f:
    data = json.load(f)
    if data.get('ok'):
        pdf_bytes = base64.b64decode(data['pdf_base64'])
        with open('test-output.pdf', 'wb') as out:
            out.write(pdf_bytes)
        print('✓ Test PDF saved as test-output.pdf')
"
else
    echo ""
    echo "✗ Test conversion failed!"
fi

rm test-payload.json response.json

echo ""
echo "========================================"
echo "✓ Deployment Complete!"
echo "========================================"
echo ""
echo "Function ARN:"
aws lambda get-function --function-name $FUNCTION_NAME --region $REGION --query 'Configuration.FunctionArn' --output text
echo ""
echo "Next steps:"
echo "1. Set environment variables in your backend:"
echo "   OFFICE_PDF_LAMBDA_FUNCTION_NAME=$FUNCTION_NAME"
echo "   OFFICE_PDF_LAMBDA_REGION=$REGION"
echo ""
echo "2. Ensure your ECS task role has permission to invoke this Lambda:"
echo "   aws iam put-role-policy \\"
echo "     --role-name <your-ecs-task-role> \\"
echo "     --policy-name InvokeLambda \\"
echo "     --policy-document file://ecs-lambda-invoke-policy.json"
echo ""
