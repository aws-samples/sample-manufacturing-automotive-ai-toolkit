#!/bin/bash

# Default configuration
export STACK_NAME="MA3TMainStack"
# Get AWS CLI's configured region, fallback to us-west-2
CLI_REGION=$(aws configure get region 2>/dev/null || echo '')
export REGION="${AWS_DEFAULT_REGION:-${CLI_REGION:-us-west-2}}"

# Parse command line arguments
SKIP_NAG=false
AUTH_USER=""
AUTH_PASSWORD=""
ACCOUNT=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --stack-name)
      STACK_NAME="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    --skip-nag)
      SKIP_NAG=true
      shift
      ;;
    --auth-user)
      AUTH_USER="$2"
      shift 2
      ;;
    --auth-password)
      AUTH_PASSWORD="$2"
      shift 2
      ;;
    --account)
      ACCOUNT="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--stack-name NAME] [--region REGION] [--skip-nag] [--auth-user USER] [--auth-password PASSWORD] [--account ACCOUNT]"
      exit 1
      ;;
  esac
done

# Prompt for auth credentials if not provided
if [ -z "$AUTH_USER" ]; then
  read -p "Enter UI username: " AUTH_USER
fi
if [ -z "$AUTH_PASSWORD" ]; then
  while true; do
    read -s -p "Enter UI password: " AUTH_PASSWORD
    echo
    read -s -p "Confirm UI password: " AUTH_PASSWORD_CONFIRM
    echo
    if [ "$AUTH_PASSWORD" = "$AUTH_PASSWORD_CONFIRM" ]; then
      break
    else
      echo "Passwords do not match. Please try again."
    fi
  done
fi

# Validate region for AgentCore compatibility
VALID_REGIONS=("us-east-1" "us-west-2" "eu-central-1" "ap-southeast-2")
if [[ ! " ${VALID_REGIONS[@]} " =~ " ${REGION} " ]]; then
  echo "Warning: Region '$REGION' is not supported by AgentCore."
  echo "Falling back to us-west-2 (default supported region)."
  echo "Supported regions are:"
  echo "  us-east-1 (US East - N. Virginia)"
  echo "  us-west-2 (US West - Oregon)"
  echo "  eu-central-1 (Europe - Frankfurt)"
  echo "  ap-southeast-2 (Asia Pacific - Sydney)"
  export REGION="us-west-2"
fi

echo "Deploying MA3T Toolkit with CDK"
echo "  Stack Name: $STACK_NAME"
echo "  Region: $REGION"

# Deploy CDK stack first
echo "Deploying CDK stack..."
cd cdk

# Set environment variable to skip cdk-nag if requested
if [ "$SKIP_NAG" = true ]; then
  echo "Skipping cdk-nag checks..."
  export CDK_NAG_SKIP=true
fi

# Pass auth credentials to CDK
export AUTH_USER="$AUTH_USER"
export AUTH_PASSWORD="$AUTH_PASSWORD"

# Set account for all CDK apps if specified
if [ -n "$ACCOUNT" ]; then
  export CDK_DEFAULT_ACCOUNT="$ACCOUNT"
  cdk deploy --require-approval never --context region="$REGION" --context account="$ACCOUNT"
else
  cdk deploy --require-approval never --context region="$REGION"
fi

# Check if the deployment was successful
if [ $? -eq 0 ]; then
  echo "CDK stack deployment successful!"
  
  # Get the S3 bucket name from CDK outputs
  S3_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='ResourceBucketName'].OutputValue" \
    --output text \
    --region "$REGION")
  
  if [ -z "$S3_BUCKET" ]; then
    echo "Error: Could not get S3 bucket name from stack outputs"
    exit 1
  fi
  
  echo "Using S3 bucket: $S3_BUCKET"
  
  # Go back to project root
  cd ..
  
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
    -x "*.zip" \
    -x "./cdk/*" \
    -x "*.pyc" \
    -x ".kiro/*" \
    -x ".vscode/*" \
    -x ".DS_Store"
  
  # Upload the zip file to S3 with the key "repo"
  echo "Uploading zip file to S3..."
  aws s3 cp "$ZIP_FILE" "s3://$S3_BUCKET/repo" --region "$REGION"
  
  echo "Local code uploaded to s3://$S3_BUCKET/repo"
  
  # Clean up the temporary directory
  rm -rf "$TEMP_DIR"
  
  # Get the CodeBuild project name for AgentCore deployment
  CODEBUILD_PROJECT=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='AgentCoreDeploymentProject'].OutputValue" \
    --output text \
    --region "$REGION")
  
  # Start the CodeBuild project to deploy the agents
  if [ ! -z "$CODEBUILD_PROJECT" ]; then
    echo "Starting CodeBuild project to deploy AgentCore agents: $CODEBUILD_PROJECT"
    BUILD_ID=$(aws codebuild start-build --project-name "$CODEBUILD_PROJECT" --region "$REGION" --query "build.id" --output text)
    
    if [ ! -z "$BUILD_ID" ]; then
      echo "CodeBuild started with ID: $BUILD_ID"
      echo "Waiting for build to complete..."
      
      # Wait for build to complete and show progress
      while true; do
        BUILD_STATUS=$(aws codebuild batch-get-builds --ids "$BUILD_ID" --region "$REGION" --query 'builds[0].buildStatus' --output text)
        
        case $BUILD_STATUS in
          "SUCCEEDED")
            echo "✅ CodeBuild completed successfully!"
            
            # Get App Runner service URL
            echo "Getting App Runner service URL..."
            SERVICE_URL=$(aws apprunner list-services --region "$REGION" --query "ServiceSummaryList[?ServiceName=='ma3t-ui-service'].ServiceUrl" --output text)
            
            if [ ! -z "$SERVICE_URL" ] && [ "$SERVICE_URL" != "None" ]; then
              echo ""
              echo "🌐 MA3T UI is available at: https://$SERVICE_URL"
              echo ""
            else
              echo "⚠️  App Runner service URL not found"
            fi
            
            break
            ;;
          "FAILED"|"FAULT"|"STOPPED"|"TIMED_OUT")
            echo "❌ CodeBuild failed with status: $BUILD_STATUS"
            echo "Check the CodeBuild logs for details: https://console.aws.amazon.com/codesuite/codebuild/projects/$CODEBUILD_PROJECT/build/$BUILD_ID"
            exit 1
            ;;
          "IN_PROGRESS")
            echo "⏳ Build in progress...(this will take ~5 minutes)"
            ;;
          *)
            echo "📋 Build status: $BUILD_STATUS"
            ;;
        esac
        
        sleep 10
      done
    else
      echo "Failed to start CodeBuild project"
      exit 1
    fi
  else
    echo "CodeBuild project not found in stack outputs"
  fi
else
  echo "CDK stack deployment failed"
  exit 1
fi

echo "CDK deployment process completed!"