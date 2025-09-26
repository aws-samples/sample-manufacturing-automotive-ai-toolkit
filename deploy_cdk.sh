#!/bin/bash

# Default configuration
export STACK_NAME="MA3TMainStack"
export REGION="${AWS_DEFAULT_REGION:-us-west-2}"

# Parse command line arguments
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
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--stack-name NAME] [--region REGION]"
      exit 1
      ;;
  esac
done

echo "Deploying MA3T Toolkit with CDK"
echo "  Stack Name: $STACK_NAME"
echo "  Region: $REGION"

# Deploy CDK stack first
echo "Deploying CDK stack..."
cd cdk
cdk deploy --require-approval never

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