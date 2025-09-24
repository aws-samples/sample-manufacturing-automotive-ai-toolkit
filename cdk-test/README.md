# MA3T CDK Implementation

This is a CDK conversion of the CloudFormation templates `infra_cfn.yml` and `build/codebuild_agentcore.yml`.

## What it creates

- **S3 Bucket**: For storing code and artifacts
- **IAM Role**: Single role with all necessary permissions for Bedrock, AgentCore, ECR, and CodeBuild
- **CodeBuild Project**: Runs the AgentCore deployment script (`scripts/build_launch_agentcore.py`)

## Deployment

```bash
./deploy.sh
```

This will:
1. Install CDK dependencies
2. Bootstrap CDK (if needed)
3. Deploy the stack
4. Upload the repo code to S3
5. Trigger the AgentCore deployment

## Manual steps

If you prefer manual deployment:

```bash
# Install dependencies
pip install -r requirements.txt

# Bootstrap CDK
cdk bootstrap

# Deploy
cdk deploy

# Upload code
BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name Ma3tStack --query "Stacks[0].Outputs[?OutputKey=='S3BucketNameOutput'].OutputValue" --output text)
cd ..
zip -r repo.zip . -x "*.git*" "*/node_modules/*" "*.venv/*" "*/__pycache__/*" "cdk.out/*" "*.zip" "cdk-test/*"
aws s3 cp repo.zip s3://$BUCKET_NAME/repo
rm repo.zip

# Trigger deployment
aws codebuild start-build --project-name Ma3tStack-agent-deployment
```

## Cleanup

```bash
cdk destroy
```
