# Vista Service Management System

A Multi-Agent Collaboration system with Supervisor Routing using AWS Bedrock agents for vehicle service management.

## Overview

This CDK application deploys a comprehensive vehicle service management system using Amazon Bedrock agents with multi-agent collaboration. The system includes:

- **Supervisor Agent**: Main orchestrator that routes requests to specialist agents
- **Specialist Agents**: 
  - Vehicle Symptom Analysis
  - Dealer Lookup
  - Appointment Booking  
  - Dealer Availability
  - Parts Availability
  - Warranty & Recalls

## Sample Prompts

Once deployed, you can test the system with these example prompts:

- **Vehicle Symptom Analysis**: "I am hearing a loud noise from my vehicle while driving. What action should I take?"
- **Dealer Lookup**: "Is there an authorized dealer near Fremont?"
- **Dealer Availability**: "What appointment slots are available at Apex Autos?"
- **Appointment Booking**: "I would like to book an appointment with Apex Autos for _June 18_ at 10:00 AM for my vehicle." [prompt with future date]
- **Parts Availability**: "Can you check if Apex Autos has the necessary parts for diagnostic trouble code P0442?"

## Prerequisites

- AWS CLI configured with appropriate credentials
- Python 3.9 or later
- Node.js (for CDK)
- AWS CDK v2 installed

## Model Configuration

**Current Model**: `anthropic.claude-3-haiku-20240307-v1:0` (Claude 3 Haiku)


## Region Configuration

The application supports flexible region configuration through multiple methods (in order of precedence):

### 1. Command Line Parameter (Highest Priority)
```bash
cd cdk && cdk deploy --region $AWS_REGION
```

### 2. Environment Variables
```bash
# Vista-specific region override
export VISTA_DEPLOY_REGION=$AWS_REGION

# Standard CDK region
export CDK_DEFAULT_REGION=$AWS_REGION

# Standard AWS region variables
export $AWS_REGION=$AWS_REGION
export AWS_DEFAULT_REGION=$AWS_REGION
```

### 3. AWS Profile/Session Region
The application will use the region from your current AWS session/profile.

### 4. Default Fallback
If no region is specified, defaults to `us-east-1`.

## Foundation Model Configuration

You can override the foundation model if needed:

### Command Line
```bash
cd cdk && cdk deploy --foundation-model anthropic.claude-3-haiku-20240307-v1:0
```

### Environment Variable
```bash
export VISTA_FOUNDATION_MODEL=anthropic.claude-3-haiku-20240307-v1:0
```

## Deployment Instructions

### Quick Start (Default Region)
```bash
# Bootstrap CDK (first time only)
cd cdk && cdk bootstrap

# Deploy the stack
cd cdk && cdk deploy --require-approval never
```

### Deploy to Specific Region (Recommended)
```bash
# For EU West 1
cd cdk && cdk bootstrap --region $AWS_REGION
cd cdk && cdk deploy --region $AWS_REGION --require-approval never

# For US East 1
cd cdk && cdk bootstrap --region us-east-1
cd cdk && cdk deploy --region us-east-1 --require-approval never

# For US West 2
cd cdk && cdk bootstrap --region us-west-2
cd cdk && cdk deploy --region us-west-2 --require-approval never
```

### Using Environment Variables
```bash
# Set target region
export CDK_DEFAULT_REGION=$AWS_REGION

# Bootstrap and deploy
cd cdk && cdk bootstrap
cd cdk && cdk deploy --require-approval never
```

### Custom Model Deployment
```bash
# Deploy with different model
cd cdk && cdk deploy --region $AWS_REGION --foundation-model anthropic.claude-3-haiku-20240307-v1:0
```

## Verification

### Check Deployment Configuration
```bash
cd cdk && cdk synth --quiet | head -10
```

### Verify Model Configuration
```bash
cd cdk && cdk synth | grep "FoundationModel"
```

### List Deployed Agents
```bash
aws bedrock-agent list-agents --region $AWS_REGION
```

## Supported Regions

The system is designed to work in any AWS region that supports:
- Amazon Bedrock with Claude 3 Haiku model
- AWS Lambda
- Amazon DynamoDB
- Amazon S3

**Tested Regions:**
- `us-east-1` (N. Virginia)
- `us-west-2` (Oregon)  
- `$AWS_REGION` (Ireland)

## Troubleshooting

### Region-Related Issues

1. **Model Not Available**: If you get model availability errors, verify the Claude 3 Haiku model is available in your target region:
   ```bash
   aws bedrock list-foundation-models --region $AWS_REGION --query 'modelSummaries[?contains(modelId, `claude-3-haiku`)]'
   ```

2. **Bootstrap Issues**: If CDK bootstrap fails, try:
   ```bash
   cd cdk && cdk bootstrap --region $AWS_REGION --force
   ```

3. **Region Mismatch**: Ensure your AWS credentials and CDK are targeting the same region:
   ```bash
   aws sts get-caller-identity
   aws configure get region
   ```

### Debug Region Selection
The application provides detailed debug output showing region selection:
```bash
cd cdk && cdk synth 2>&1 | head -15
```

Look for these debug lines:
- `🔍 Debug - CLI region`
- `🔍 Debug - VISTA_DEPLOY_REGION`  
- `🔍 Debug - CDK_DEFAULT_REGION`
- `✅ Using Deployment Region`

## Clean Up

### Destroy Resources
```bash
# Destroy in specific region
cd cdk && cdk destroy --region $AWS_REGION

# Or use environment variable
export CDK_DEFAULT_REGION=$AWS_REGION
cd cdk && cdk destroy
```

## Architecture

The system deploys:

- **7 Bedrock Agents** using Claude 3 Haiku model
- **Lambda Functions** for action group implementations
- **DynamoDB Tables** for data storage  
- **S3 Bucket** for resources
- **IAM Roles** with appropriate permissions

All components are deployed in the same region specified during deployment.

## Security

- IAM roles follow least privilege principle
- AWS credentials are never committed to git (see `.gitignore`)
- All inter-service communication uses AWS IAM authentication

## Contributing

1. Make changes to CDK code
2. Test deployment: `cd cdk && cdk synth`
3. Deploy to test region: `cd cdk && cdk deploy --region us-east-1`
4. Commit changes: `git add . && git commit -m "Description"`

## Support

For issues related to:
- **Region configuration**: Check the debug output and AWS CLI configuration
- **Model availability**: Verify Bedrock model availability in your target region  
- **Deployment failures**: Check CloudFormation events in AWS Console
