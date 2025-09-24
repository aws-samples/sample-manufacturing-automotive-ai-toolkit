#!/bin/bash

set -e

echo "Installing CDK dependencies..."
pip install -r requirements.txt

echo "Bootstrapping CDK..."
cdk bootstrap

echo "Deploying MA3T stack..."
cdk deploy --require-approval never

echo "Getting S3 bucket name..."
BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name Ma3tStack --query "Stacks[0].Outputs[?OutputKey=='S3BucketNameOutput'].OutputValue" --output text)

echo "Uploading code to S3 bucket: $BUCKET_NAME"
cd ..
zip -r repo.zip . -x "*.git*" "*/node_modules/*" "*.venv/*" "*/__pycache__/*" "cdk.out/*" "*.zip" "cdk-test/*"
aws s3 cp repo.zip s3://$BUCKET_NAME/repo
rm repo.zip

echo "Triggering AgentCore deployment..."
aws codebuild start-build --project-name Ma3tStack-agent-deployment

echo "Deployment complete!"
