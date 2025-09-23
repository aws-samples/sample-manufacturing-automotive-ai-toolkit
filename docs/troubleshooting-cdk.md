# CDK Troubleshooting Guide

## Common CDK Bootstrap Issues

### Issue: "SSM parameter /cdk-bootstrap/hnb659fds/version not found"

This error indicates that CDK bootstrap didn't complete successfully or the bootstrap stack was deleted.

#### Solution 1: Manual Bootstrap with Explicit Parameters

```bash
# Get your account ID and region
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region)

# Bootstrap with explicit parameters
cd cdk
cdk bootstrap aws://$ACCOUNT_ID/$REGION --verbose
```

#### Solution 2: Check Bootstrap Stack Status

```bash
# Check if CDKToolkit stack exists
aws cloudformation describe-stacks --stack-name CDKToolkit --region us-west-2

# If it exists but is in a failed state, delete and recreate
aws cloudformation delete-stack --stack-name CDKToolkit --region us-west-2

# Wait for deletion to complete, then bootstrap again
cdk bootstrap
```

#### Solution 3: Bootstrap with Custom Qualifier

If you have multiple CDK applications, you might need a custom qualifier:

```bash
# Bootstrap with custom qualifier
cdk bootstrap --qualifier ma3ttool

# Then deploy with the same qualifier
cdk deploy --qualifier ma3ttool
```

#### Solution 4: Check IAM Permissions

Ensure your AWS credentials have the following permissions:
- `cloudformation:*`
- `s3:*`
- `iam:*`
- `ssm:*`
- `ecr:*`

### Issue: "current credentials could not be used to assume role"

This warning can usually be ignored if you're using the correct account, but if deployment fails:

#### Solution: Use --force Flag

```bash
cdk bootstrap --force
```

#### Solution: Check AWS Profile

```bash
# Verify you're using the correct AWS profile
aws sts get-caller-identity

# If using a specific profile
export AWS_PROFILE=your-profile-name
cdk bootstrap
```

### Issue: CDK Version Compatibility

#### Solution: Update CDK CLI

```bash
# Update CDK CLI to latest version
npm install -g aws-cdk@latest

# Check version
cdk --version

# Clear CDK cache if needed
rm -rf ~/.cdk
```

### Issue: Python Virtual Environment Problems

#### Solution: Recreate Virtual Environment

```bash
cd cdk
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Quick Fix Script

Here's a script to automatically resolve common bootstrap issues:

```bash
#!/bin/bash
# fix-cdk-bootstrap.sh

set -e

echo "🔧 Fixing CDK Bootstrap Issues..."

# Get AWS account info
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=${AWS_DEFAULT_REGION:-us-west-2}

echo "Account: $ACCOUNT_ID"
echo "Region: $REGION"

# Check if CDKToolkit stack exists and is in a bad state
STACK_STATUS=$(aws cloudformation describe-stacks --stack-name CDKToolkit --region $REGION --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "NOT_FOUND")

if [[ "$STACK_STATUS" == "ROLLBACK_COMPLETE" || "$STACK_STATUS" == "CREATE_FAILED" || "$STACK_STATUS" == "DELETE_FAILED" ]]; then
    echo "⚠️  CDKToolkit stack is in bad state: $STACK_STATUS"
    echo "🗑️  Deleting existing CDKToolkit stack..."
    aws cloudformation delete-stack --stack-name CDKToolkit --region $REGION
    
    echo "⏳ Waiting for stack deletion..."
    aws cloudformation wait stack-delete-complete --stack-name CDKToolkit --region $REGION
fi

# Update CDK CLI
echo "📦 Updating CDK CLI..."
npm install -g aws-cdk@latest

# Clear CDK cache
echo "🧹 Clearing CDK cache..."
rm -rf ~/.cdk

# Bootstrap CDK
echo "🚀 Bootstrapping CDK..."
cd cdk

# Recreate virtual environment
if [[ -d ".venv" ]]; then
    rm -rf .venv
fi

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Bootstrap with verbose output
cdk bootstrap aws://$ACCOUNT_ID/$REGION --verbose

echo "✅ CDK Bootstrap completed successfully!"
```

Save this as `fix-cdk-bootstrap.sh` and run:

```bash
chmod +x fix-cdk-bootstrap.sh
./fix-cdk-bootstrap.sh
```

## Alternative: Use CloudFormation Bootstrap

If CDK bootstrap continues to fail, you can manually create the bootstrap resources:

```bash
# Download the bootstrap template
curl -O https://raw.githubusercontent.com/aws/aws-cdk/main/packages/aws-cdk/lib/api/bootstrap/bootstrap-template.yaml

# Deploy using CloudFormation
aws cloudformation deploy \
  --template-file bootstrap-template.yaml \
  --stack-name CDKToolkit \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-west-2
```

## Verification Steps

After fixing bootstrap issues:

1. **Verify Bootstrap Stack:**
   ```bash
   aws cloudformation describe-stacks --stack-name CDKToolkit --region us-west-2
   ```

2. **Check SSM Parameter:**
   ```bash
   aws ssm get-parameter --name /cdk-bootstrap/hnb659fds/version --region us-west-2
   ```

3. **Test CDK Synthesis:**
   ```bash
   cd cdk
   source .venv/bin/activate
   cdk synth MA3TMainStack
   ```

4. **Test Deployment:**
   ```bash
   ./deploy_cdk.sh --diff  # Show what would be deployed
   ```

If all verification steps pass, you should be able to deploy successfully with:

```bash
./deploy_cdk.sh
```