

# Quality Inspection System Deployment Guide

## Prerequisites

- AWS CLI configured with appropriate permissions
- CDK CLI installed (`npm install -g aws-cdk`)
- Python 3.10+
- Bedrock model access enabled in your AWS account
- AgentCore CLI (automatically installed during deployment)

## Quick Start - Complete Deployment

### Two-Phase Deployment

The system uses a two-phase deployment approach:

```bash
# Deploy the complete system with one command
AWS_PROFILE=your-profile ./deploy_full_stack_quality_inspection.sh
```

This script automatically executes both phases:

#### Phase 1: Infrastructure Deployment
- **CDK Stack**: Deploys AWS infrastructure (S3, DynamoDB, VPC, SNS, IAM roles)
- **Prerequisites Check**: Validates AWS CLI, CDK, Python environment
- **CDK Bootstrap**: Initializes CDK in your account if needed

#### Phase 2: AgentCore Deployment
- **AgentCore CLI Installation**: Installs bedrock-agentcore-starter-toolkit
- **Agent Configuration**: Configures 6 agents with proper entrypoints
- **Agent Launch**: Deploys agents to AgentCore with auto-update capability
- **Results Documentation**: Generates deployment results with Runtime ARNs

### What Gets Deployed

The deployment creates:
- **S3 Bucket**: `machinepartimages-{account-id}` for image storage
- **DynamoDB Tables**: 6 tables for agent data and audit trails
- **AgentCore Runtimes**: 6 managed agent runtimes with ECR repositories
- **VPC & Security**: Isolated network with proper security groups
- **SNS Topic**: Quality inspection alerts
- **IAM Roles**: Least-privilege permissions for all components

### Deployment Output

Successful deployment shows:
```
[SUCCESS] === DEPLOYMENT COMPLETED SUCCESSFULLY ===

Key Resources Created:
  • S3 Bucket: machinepartimages-123456789012
  • DynamoDB Tables: vision-inspection-data, sop-decisions, action-execution-log, etc.
  • AgentCore Runtimes: 6 agent runtimes deployed
  • VPC: vpc-agentic-quality-inspection
  • SNS Topic: quality-inspection-alerts

Next Steps:
  1. Check agentcore_deployment_results.md for ECR repositories and Runtime ARNs
  2. Upload test images to s3://machinepartimages-{account-id}/inputimages/
  3. Monitor CloudWatch logs for agent execution
  4. Check DynamoDB tables for inspection results
  5. Review SNS notifications for quality alerts
```

## Manual Deployment (Advanced)

If you need to deploy components individually:

### 1. Enable Bedrock Model Access
```bash
# Request access to Amazon Nova Pro model via AWS Console:
# Bedrock > Model access > Request model access
```

### 2. Deploy Infrastructure (CDK)

```bash
# Navigate to infrastructure directory
cd infrastructure

# Install CDK dependencies
pip install -r requirements.txt

# Bootstrap CDK (first time only)
cdk bootstrap --profile your-profile

# Deploy the infrastructure stack
cdk deploy --profile your-profile --require-approval never
```

### 3. Deploy AgentCore Agents

```bash
# Run the AgentCore deployment script
AWS_PROFILE=your-profile ./quality_inspection_agentcore_deploy.sh
```

### 4. Verify Infrastructure

```bash
# Get your account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Check S3 bucket
aws s3 ls s3://machinepartimages-$ACCOUNT_ID

# Check DynamoDB table
aws dynamodb describe-table --table-name vision-inspection-data

# Reference image is automatically uploaded by CDK from tests/test_images/reference_image/
```

## AgentCore Runtime Updates

After initial deployment, you can update individual agent runtimes when you modify agent code:

### Update Individual Agents

Navigate to the agents directory:
```bash
cd src/agents
```

#### Update Any Agent Runtime
```bash
# Update Vision Agent
agentcore launch --agent quality_inspection_vision --auto-update-on-conflict

# Update Orchestrator Agent
agentcore launch --agent quality_inspection_orchestrator --auto-update-on-conflict

# Update SOP Agent
agentcore launch --agent quality_inspection_sop --auto-update-on-conflict

# Update Action Agent
agentcore launch --agent quality_inspection_action --auto-update-on-conflict

# Update Communication Agent
agentcore launch --agent quality_inspection_communication --auto-update-on-conflict

# Update Analysis Agent
agentcore launch --agent quality_inspection_analysis --auto-update-on-conflict
```

*Each `agentcore launch` command automatically handles the complete update pipeline: container build → ECR push → runtime redeployment.*

### Monitor Update Status

The `agentcore launch` command provides real-time update monitoring and will show:
- Container build completion
- ECR push success
- Runtime update status
- Final agent ARN and endpoints

For additional monitoring:
```bash
# Check agent status
agentcore status --agent <agent-name>

# Test agent deployment
agentcore invoke --agent <agent-name> '{"prompt": "Hello"}'
```

## Verification

### Test Agent Deployment

```bash
# Get runtime ARN from deployment results
cat agentcore_deployment_results.md

# Test orchestrator agent (replace with actual ARN from results)
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/quality_inspection_orchestrator-xxxxx" \
  --runtime-session-id "test-session-$(date +%s)" \
  --payload '{"prompt": "System status check"}'
```

### Run Streamlit Application

```bash
# From project root
streamlit run src/demo_app/quality-inspection-streamlit-demo.py
```

## Key Resources

### Get Resource Information

```bash
# Get your account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Get CDK stack outputs
aws cloudformation describe-stacks --stack-name AgenticQualityInspectionStack --query "Stacks[0].Outputs"

# Key resources:
# - S3 Bucket: machinepartimages-$ACCOUNT_ID
# - DynamoDB Table: vision-inspection-data
# - Agent Runtime ARNs: (from agentcore_deployment_results.md)
```

## Troubleshooting

### Common Issues

1. **AgentCore CLI Installation**: If `agentcore` command not found, run `pip install bedrock-agentcore-starter-toolkit`
2. **Permission Errors**: Verify IAM roles have required permissions
3. **Agent Launch Failures**: Check agent configuration and entrypoint files

### Debug Commands

```bash
# Check agent status
agentcore status --agent <agent-name>

# View recent DynamoDB entries
aws dynamodb scan --table-name vision-inspection-data --limit 5

# Check S3 bucket contents
aws s3 ls s3://machinepartimages-{account-id}/ --recursive
```

## Complete System Redeployment

To redeploy the entire system (infrastructure + agents):

```bash
# Complete redeployment
AWS_PROFILE=your-profile ./deploy_full_stack_quality_inspection.sh
```

### Individual Agent Updates

To update specific agents after code changes:

```bash
# Navigate to agents directory
cd src/agents

# Update specific agent
agentcore launch --agent <agent-name> --auto-update-on-conflict

# Example: Update communication agent
agentcore launch --agent quality_inspection_communication --auto-update-on-conflict
```

### Update Pipeline Details

The `agentcore launch` command automatically:
1. **Container Build**: Creates Docker image from latest agent code
2. **ECR Push**: Uploads image to dedicated ECR repository
3. **Runtime Update**: Redeploys AgentCore runtime with new container version
4. **Verification**: Validates successful deployment and provides runtime ARN

## Cleanup

```bash
# Destroy CDK stack
cd infrastructure
cdk destroy --profile your-profile

# Note: AgentCore agents must be manually deleted through AWS Console
# Go to Bedrock > AgentCore > Agents to delete individual agents
```

## Additional Deployment Options

### Streamlit Cloud Deployment

For deploying the Streamlit demo application to AWS cloud infrastructure (ECS Fargate), see the dedicated guide:

📖 **[Streamlit Cloud Deployment Guide](STREAMLIT_DEPLOYMENT.md)**

This guide covers:
- ECS Fargate deployment with CDK
- Application Load Balancer setup
- VPC integration with the main system
- Environment configuration for cloud deployment