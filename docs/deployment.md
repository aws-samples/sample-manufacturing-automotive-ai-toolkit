# Deployment Guide

This guide explains how agents are deployed in MA3T.

## Quick Deployment

```bash
./deploy_cdk.sh
```

This deploys all agents and infrastructure to AWS.

## Deployment Process

### 1. Agent Discovery
The framework scans `agents_catalog/` for `manifest.json` files.

### 2. Infrastructure Deployment
For agents with `infrastructure.cdk: true`:
- Creates a nested CDK stack
- Deploys AWS resources (DynamoDB, S3, etc.)
- Auto-grants permissions to shared agent role

### 3. AgentCore Deployment
For AgentCore agents:
- Builds Docker container
- Pushes to ECR
- Deploys to AWS (ECS/Lambda)
- Registers with Bedrock AgentCore

### 4. UI Registration
All agents are automatically registered in the web UI.

## Deployment Options

### Basic Deployment
```bash
./deploy_cdk.sh
```

### With Custom Credentials
```bash
./deploy_cdk.sh --auth-user admin --auth-password mypassword
```

### Custom Region
```bash
./deploy_cdk.sh --region us-east-1
```

### Skip Security Checks (Development)
```bash
./deploy_cdk.sh --skip-nag
```

### All Options
```bash
./deploy_cdk.sh \
  --region us-west-2 \
  --account 123456789012 \
  --auth-user admin \
  --auth-password secretpass \
  --stack-name MyStack \
  --skip-nag
```

## Supported Regions

Due to AgentCore restrictions, only these regions are supported:
- `us-east-1` (US East - N. Virginia)
- `us-west-2` (US West - Oregon) - **default**
- `eu-central-1` (Europe - Frankfurt)
- `ap-southeast-2` (Asia Pacific - Sydney)

## What Gets Deployed

### Main Stack
- IAM roles and policies
- S3 buckets for resources
- CodeBuild projects for AgentCore deployment
- UI infrastructure (App Runner)

### Nested Stacks
One per agent with infrastructure:
- DynamoDB tables
- S3 buckets
- Lambda functions
- Other AWS resources

### AgentCore Containers
For each AgentCore agent:
- Docker container with agent code
- ECR repository
- ECS task or Lambda function

### UI
- Next.js application on App Runner
- Basic authentication
- Agent discovery and registration

## Deployment Flow

```
1. CDK Synthesis
   ├── Discover agents from manifest.json
   ├── Create nested stacks for infrastructure
   └── Generate CloudFormation templates

2. CloudFormation Deployment
   ├── Deploy main stack
   ├── Deploy nested stacks (parallel)
   └── Auto-grant permissions

3. CodeBuild Execution
   ├── Build AgentCore containers
   ├── Push to ECR
   └── Deploy to Bedrock AgentCore

4. UI Deployment
   ├── Build Next.js app
   ├── Deploy to App Runner
   └── Register agents
```

## Monitoring Deployment

### CloudFormation Console
Watch stack creation progress:
```
AWS Console → CloudFormation → Stacks → MA3TMainStack
```

### CodeBuild Logs
View AgentCore deployment logs:
```
AWS Console → CodeBuild → Build projects → AgentCore-Deployment
```

### CDK Output
The deployment script shows:
- Stack creation progress
- Resource ARNs
- UI URL
- Deployment status

## Post-Deployment

### Access the UI
The deployment outputs the UI URL:
```
MA3TMainStack.UIUrl = https://xxxxx.us-west-2.awsapprunner.com
```

### Verify Agents
Check that all agents appear in the UI.

### Test Agents
Use the chat interface to test each agent.

## Updating Agents

### Update Agent Code
1. Modify your agent code
2. Run `./deploy_cdk.sh`
3. Only changed resources are updated

### Update Infrastructure
1. Modify `cdk/stack.py`
2. Run `./deploy_cdk.sh`
3. CloudFormation updates the stack

### Add New Agent
1. Create agent folder with `manifest.json`
2. Run `./deploy_cdk.sh`
3. New agent is automatically discovered and deployed

## Cleanup

### Destroy Everything
```bash
cdk destroy --context region=us-west-2
```

### Destroy Specific Stack
```bash
cdk destroy MA3TMainStack --context region=us-west-2
```

### Manual Cleanup
If CDK destroy fails:
1. Go to CloudFormation console
2. Delete `MA3TMainStack`
3. Delete any remaining nested stacks
4. Empty and delete S3 buckets manually if needed

## Troubleshooting Deployment

### Stack Creation Failed
- Check CloudFormation events for error details
- Verify AWS credentials and permissions
- Ensure region is supported
- Check for resource name conflicts

### AgentCore Deployment Failed
- Check CodeBuild logs
- Verify Docker builds locally
- Check ECR permissions
- Ensure agent code has no syntax errors

### UI Not Accessible
- Check App Runner service status
- Verify security group rules
- Check authentication credentials
- Review App Runner logs

### Permission Errors
- Verify IAM roles have correct permissions
- Check resource policies
- Ensure auto-grant framework ran
- Review CloudWatch logs

## Best Practices

### Development
- Use `--skip-nag` for faster iterations
- Test locally before deploying
- Deploy to a dev account first

### Production
- Don't use `--skip-nag`
- Enable point-in-time recovery for DynamoDB
- Use strong authentication credentials
- Enable CloudWatch logging
- Set up monitoring and alerts

### CI/CD
- Automate deployments with GitHub Actions
- Use separate accounts for dev/staging/prod
- Run tests before deployment
- Tag releases

## Next Steps

- [Adding Agents](adding-agents.md) - Create new agents
- [Infrastructure Setup](infrastructure-setup.md) - Add AWS resources
- [Troubleshooting](troubleshooting.md) - Debug issues
