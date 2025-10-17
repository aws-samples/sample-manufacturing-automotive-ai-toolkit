#!/bin/bash

# Get region from environment or default
REGION="${AWS_DEFAULT_REGION:-us-west-2}"

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
