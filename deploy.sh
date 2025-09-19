#!/bin/bash

# Load environment variables from .env file if it exists
if [ -f .env ]; then
  echo "Loading configuration from .env file..."
  export $(grep -v '^#' .env | xargs)
else
  echo "Warning: .env file not found. Using default values."
  echo "Please copy .env.example to .env and customize the values."
  
  # Default configuration (fallback values)
  export STACK_NAME="ma3t-toolkit-stack"
  export S3_BUCKET="ma3t-toolkit-$(aws sts get-caller-identity --query Account --output text)-${AWS_DEFAULT_REGION:-us-west-2}"
  export TEMP_BUCKET="ma3t-toolkit-temp-$(aws sts get-caller-identity --query Account --output text)-${AWS_DEFAULT_REGION:-us-west-2}"
  export REGION="${AWS_DEFAULT_REGION:-us-west-2}"
  export CODE_PREFIX="repo"
  export VISTA_DEPLOY_REGION="${AWS_DEFAULT_REGION:-us-west-2}"
fi

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --stack-name)
      STACK_NAME="$2"
      shift 2
      ;;
    --bucket)
      S3_BUCKET="$2"
      shift 2
      ;;
    --temp-bucket)
      TEMP_BUCKET="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--stack-name NAME] [--bucket BUCKET] [--temp-bucket TEMP_BUCKET] [--region REGION]"
      exit 1
      ;;
  esac
done

echo "Deploying MA3T Toolkit"
echo "  Stack Name: $STACK_NAME"
echo "  S3 Bucket: $S3_BUCKET"
echo "  Temp Bucket: $TEMP_BUCKET"
echo "  Region: $REGION"

# Check if the S3 bucket exists, create it if it doesn't
if ! aws s3api head-bucket --bucket "$S3_BUCKET" --region "$REGION" 2>/dev/null; then
  echo "Creating S3 bucket: $S3_BUCKET"
  aws s3 mb "s3://$S3_BUCKET" --region "$REGION"
  
  # Block public access
  aws s3api put-public-access-block \
    --bucket "$S3_BUCKET" \
    --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
    --region "$REGION"
else
  echo "S3 bucket already exists: $S3_BUCKET"
fi

# Check if the temp bucket exists, create it if it doesn't
if ! aws s3api head-bucket --bucket "$TEMP_BUCKET" --region "$REGION" 2>/dev/null; then
  echo "Creating temp S3 bucket: $TEMP_BUCKET"
  aws s3 mb "s3://$TEMP_BUCKET" --region "$REGION"
  
  # Block public access
  aws s3api put-public-access-block \
    --bucket "$TEMP_BUCKET" \
    --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
    --region "$REGION"
else
  echo "Temp S3 bucket already exists: $TEMP_BUCKET"
fi

# Create a temporary directory for the zip file
TEMP_DIR=$(mktemp -d)
ZIP_FILE="$TEMP_DIR/repo.zip"

echo "Creating zip file of local code..."
zip -r "$ZIP_FILE" . \
  -x "*.git*" \
  -x "*/node_modules/*" \
  -x "ui/node_modules/*" \
  -x "*.aws-sam/*" \
  -x "ui/.next/*" \
  -x "*.venv/*" \
  -x "*/.venv/*" \
  -x "*/*/.venv/*" \
  -x "*/*/*/.venv/*" \
  -x "*/*/*/*/.venv/*" \
  -x "*/__pycache__/*" \
  -x "*/*/__pycache__/*" \
  -x "*/*/*/__pycache__/*" \
  -x "*/*/*/*/__pycache__/*" \
  -x "*.zip"

# Upload the zip file to S3 with the key "repo" (not "repo.zip")
echo "Uploading zip file to S3..."
aws s3 cp "$ZIP_FILE" "s3://$S3_BUCKET/$CODE_PREFIX" --region "$REGION"

echo "Local code uploaded to s3://$S3_BUCKET/$CODE_PREFIX"

# Clean up the temporary directory
rm -rf "$TEMP_DIR"

# Package CloudFormation template
echo "Packaging CloudFormation template..."
aws cloudformation package \
  --template-file "infra_cfn.yaml" \
  --s3-bucket "$TEMP_BUCKET" \
  --output-template-file "packaged_infra_cfn.yaml" \
  --region "$REGION"

# Deploy CloudFormation stack
echo "Deploying CloudFormation stack..."
aws cloudformation deploy \
  --template-file "packaged_infra_cfn.yaml" \
  --s3-bucket "$TEMP_BUCKET" \
  --capabilities CAPABILITY_IAM \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --parameter-overrides \
    DeployApplication=false \
    UseLocalCode=true \
    S3BucketName="$S3_BUCKET"

# Check if the deployment was successful
if [ $? -eq 0 ]; then
  echo "Stack deployment successful!"
  
  # Get the CodeBuild project name
  CODEBUILD_PROJECT=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='AgentCoreDeploymentProject'].OutputValue" \
    --output text \
    --region "$REGION")
  
  # Start the CodeBuild project to deploy the agents
  if [ ! -z "$CODEBUILD_PROJECT" ]; then
    echo "Starting CodeBuild project to deploy agents: $CODEBUILD_PROJECT"
    aws codebuild start-build --project-name "$CODEBUILD_PROJECT" --region "$REGION"
  else
    echo "CodeBuild project not found in stack outputs"
  fi
else
  echo "Stack deployment failed"
fi

echo "Deployment process completed!"
