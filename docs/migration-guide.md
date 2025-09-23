# Migration Guide: CloudFormation to CDK

This guide provides step-by-step instructions for migrating from the CloudFormation-based deployment to the new CDK-based deployment system.

## Overview

The MA3T toolkit has been migrated from CloudFormation templates to AWS CDK for better maintainability, type safety, and developer experience. This migration provides:

- **Type Safety**: CDK's TypeScript/Python type system catches errors at compile time
- **Better Abstractions**: Higher-level constructs reduce boilerplate code
- **Improved Testing**: Unit testing capabilities for infrastructure code
- **Enhanced Developer Experience**: IDE support with autocomplete and documentation

## Migration Steps

### 1. Prerequisites

Before starting the migration, ensure you have:

- AWS CLI configured with appropriate permissions
- Node.js (v14 or later) and npm installed
- CDK CLI installed: `npm install -g aws-cdk`
- Python 3.8+ (for CDK Python constructs)

### 2. Backup Current Deployment

Before migrating, document your current CloudFormation stack:

```bash
# Export current stack template
aws cloudformation get-template \
  --stack-name your-stack-name \
  --template-stage Processed \
  --query 'TemplateBody' > backup-template.json

# Export current stack parameters
aws cloudformation describe-stacks \
  --stack-name your-stack-name \
  --query 'Stacks[0].Parameters' > backup-parameters.json

# Export current stack outputs
aws cloudformation describe-stacks \
  --stack-name your-stack-name \
  --query 'Stacks[0].Outputs' > backup-outputs.json
```

### 3. Bootstrap CDK Environment

CDK requires a bootstrap stack in your AWS account:

```bash
./deploy_cdk.sh --bootstrap
```

This creates the necessary S3 buckets and IAM roles for CDK deployments.

### 4. Deploy Using CDK

#### Option A: Fresh Deployment (Recommended)

If you can afford downtime, the cleanest approach is to:

1. Delete the existing CloudFormation stack:
   ```bash
   aws cloudformation delete-stack --stack-name your-old-stack-name
   ```

2. Deploy using CDK:
   ```bash
   ./deploy_cdk.sh --stack-name MA3TMainStack
   ```

#### Option B: Side-by-Side Deployment

For zero-downtime migration:

1. Deploy CDK stack with a different name:
   ```bash
   ./deploy_cdk.sh --stack-name MA3TMainStack-New
   ```

2. Test the new deployment thoroughly

3. Update DNS/routing to point to new resources

4. Delete the old CloudFormation stack

### 5. Verify Migration

After deployment, verify that all components are working:

```bash
# Check stack status
aws cloudformation describe-stacks --stack-name MA3TMainStack

# Test agent endpoints
# (Use the outputs from the stack to get endpoint URLs)

# Verify S3 buckets and Lambda functions are accessible
```

## Key Differences

### Deployment Commands

| Aspect | CloudFormation | CDK |
|--------|----------------|-----|
| Deploy | `./deploy.sh` | `./deploy_cdk.sh` |
| Template | `infra_cfn.yaml` | `cdk/` directory |
| Parameters | Command line args | Command line args + context |
| Bootstrap | Not required | `./deploy_cdk.sh --bootstrap` |

### Parameter Mapping

The CDK deployment supports the same parameters as CloudFormation:

| Parameter | CloudFormation | CDK |
|-----------|----------------|-----|
| Stack Name | `--stack-name` | `--stack-name` |
| S3 Bucket | `--bucket` | `--bucket` |
| Region | `--region` | `--region` |
| Bedrock Model | N/A | `--bedrock-model` |
| Deploy Application | N/A | `--deploy-app` |
| Use Local Code | N/A | `--use-local-code` |
| Deploy Vista Agents | N/A | `--deploy-vista` |

### New CDK-Only Features

The CDK deployment includes additional capabilities:

- **Hotswap Deployments**: Faster updates for development (`--hotswap`)
- **Diff Preview**: See changes before deployment (`--diff`)
- **Better Error Handling**: More detailed error messages and rollback
- **Type Safety**: Compile-time validation of infrastructure code

## Troubleshooting

### Common Migration Issues

#### 1. CDK Bootstrap Required

**Error**: `SSM parameter /cdk-bootstrap/hnb659fds/version not found`

**Solution**: Run CDK bootstrap:
```bash
./deploy_cdk.sh --bootstrap
```

#### 2. Resource Name Conflicts

**Error**: Resource already exists with different configuration

**Solution**: Use a different stack name or delete conflicting resources:
```bash
./deploy_cdk.sh --stack-name MA3TMainStack-New
```

#### 3. Permission Issues

**Error**: Access denied or insufficient permissions

**Solution**: Ensure your AWS credentials have the necessary permissions:
- CloudFormation full access
- IAM role creation/management
- S3 bucket creation/management
- Lambda function deployment
- Bedrock service access

#### 4. Python Virtual Environment Issues

**Error**: CDK dependencies not found

**Solution**: The script automatically creates a virtual environment, but you can manually set it up:
```bash
cd cdk
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 5. Region-Specific Issues

**Error**: Service not available in region

**Solution**: Some AWS services have regional limitations. Ensure your target region supports:
- Amazon Bedrock
- AWS Lambda
- Amazon S3
- AWS CodeBuild

### Getting Help

If you encounter issues during migration:

1. Check the deployment logs for specific error messages
2. Verify your AWS credentials and permissions
3. Ensure all prerequisites are installed
4. Try deploying to a different region if you suspect regional issues
5. Use the `--diff` flag to preview changes before deployment

### Rollback Procedure

If you need to rollback to CloudFormation:

1. Delete the CDK stack:
   ```bash
   ./deploy_cdk.sh --destroy
   ```

2. Redeploy using CloudFormation:
   ```bash
   ./deploy.sh --stack-name your-original-stack-name
   ```

## Post-Migration

After successful migration:

1. **Update Documentation**: Update any internal documentation to reference CDK commands
2. **Update CI/CD**: Modify deployment pipelines to use `deploy_cdk.sh`
3. **Team Training**: Ensure team members understand CDK deployment process
4. **Monitor**: Keep an eye on the deployment for the first few days to catch any issues

## Benefits Realized

After migration, you'll benefit from:

- **Faster Deployments**: CDK's incremental updates and hotswap capabilities
- **Better Error Messages**: More descriptive error messages and stack traces
- **Type Safety**: Compile-time validation prevents many runtime errors
- **Easier Maintenance**: Modular, reusable infrastructure components
- **Enhanced Testing**: Unit tests for infrastructure code
- **IDE Support**: Autocomplete, documentation, and refactoring tools

## Next Steps

Consider these enhancements after migration:

1. **Infrastructure Testing**: Implement unit tests for CDK constructs
2. **Multi-Environment**: Set up separate stacks for dev/staging/prod
3. **CI/CD Integration**: Automate deployments using CDK in your CI/CD pipeline
4. **Custom Constructs**: Create reusable constructs for common patterns
5. **Monitoring**: Implement infrastructure monitoring and alerting