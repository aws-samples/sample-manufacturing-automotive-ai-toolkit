#!/bin/bash

# Default configuration
STACK_NAME="MA3TMainStack"
# Get region from environment, AWS profile default, or fallback
PROFILE_REGION=$(aws configure get region 2>/dev/null || echo "")
REGION="${AWS_DEFAULT_REGION:-${PROFILE_REGION:-us-west-2}}"

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

# Check if this is a Quality Inspection destroy
if [ "$STACK_NAME" = "QualityInspectionStack" ]; then
  echo "Quality Inspection stack detected. Redirecting to specialized destroy script..."
  echo "  Stack Name: $STACK_NAME"
  echo "  Region: $REGION"
  
  # Set environment variables for the quality inspection script
  export AWS_REGION="$REGION"
  
  # Run the quality inspection destroy script with --force flag
  exec bash "./agents_catalog/multi_agent_collaboration/02-quality_inspection_agentcore/deploy/destroy_full_stack_quality_inspection.sh" --force
fi

echo "Checking for Quality Inspection stack..."

# Check if Quality Inspection stack exists
QI_STACK_NAME="AgenticQualityInspectionStack"
if aws cloudformation describe-stacks --stack-name "$QI_STACK_NAME" --region "$REGION" &>/dev/null; then
    echo "Found Quality Inspection stack: $QI_STACK_NAME"
    echo "Destroying Quality Inspection stack..."
    
    # Change to quality inspection CDK directory and destroy
    cd agents_catalog/multi_agent_collaboration/02-quality_inspection_agentcore/cdk
    cdk destroy "$QI_STACK_NAME" --force --region "$REGION"
    
    # Return to root directory
    cd ../../../..
    
    echo "Quality Inspection stack destroyed"
else
    echo "No Quality Inspection stack found"
fi

echo "Cleaning up external resources before CDK destroy..."

# Delete App Runner service
echo "Deleting App Runner service..."
SERVICE_ARN=$(aws apprunner list-services --region "$REGION" --query "ServiceSummaryList[?ServiceName=='ma3t-ui-service'].ServiceArn" --output text 2>/dev/null)

if [ ! -z "$SERVICE_ARN" ] && [ "$SERVICE_ARN" != "None" ]; then
  echo "Found App Runner service: $SERVICE_ARN"
  aws apprunner delete-service --service-arn "$SERVICE_ARN" --region "$REGION"
  echo "App Runner service deletion initiated"
  
  # Wait for deletion to complete
  echo "Waiting for App Runner service to be deleted..."
  while true; do
    STATUS=$(aws apprunner describe-service --service-arn "$SERVICE_ARN" --region "$REGION" --query "Service.Status" --output text 2>/dev/null)
    
    if [ $? -ne 0 ] || [ "$STATUS" = "None" ]; then
      echo "App Runner service successfully deleted"
      break
    elif [ "$STATUS" = "DELETED" ]; then
      echo "App Runner service successfully deleted"
      break
    else
      echo "App Runner service status: $STATUS - waiting..."
      sleep 10
    fi
  done
else
  echo "No App Runner service found"
fi

echo "Running CDK destroy..."
cd cdk
cdk destroy --all --force

echo "Cleanup completed!"
