# Streamlit Demo App Deployment Guide

## Architecture Overview

![Streamlit Demo Cloud Architecture](../../docs/streamlit_demo_cloud_deployment_architecture.png)

The Streamlit demo app is deployed using a secure, internal-only architecture:

- **ECS Fargate Service**: Runs the Streamlit container in private subnets
- **Internal Application Load Balancer**: Routes traffic to the container (port 8501)
- **Bastion Host**: Provides secure access via AWS Session Manager
- **VPC Endpoints**: Enable Session Manager connectivity without internet access

## Accessing the Application

### Prerequisites
- AWS CLI installed and configured
- Session Manager plugin installed

### Access Steps

1. **Get Port Forwarding Command**
   ```bash
   aws cloudformation describe-stacks --stack-name QualityInspectionStreamlitDemoStack --query 'Stacks[0].Outputs[?OutputKey==`PortForwardCommand`].OutputValue' --output text
   ```

2. **Start Port Forwarding**
   Use the command from step 1, or manually construct:
   ```bash
   aws ssm start-session --target <BASTION_INSTANCE_ID> --document-name AWS-StartPortForwardingSessionToRemoteHost --parameters '{"host":["<INTERNAL_ALB_HOSTNAME>"],"portNumber":["8501"],"localPortNumber":["8501"]}'
   ```

3. **Wait for Connection**
   Terminal will show: "Waiting for connections..."

4. **Open Browser**
   Navigate to: http://localhost:8501

5. **Use the Application**
   - Upload images for quality inspection
   - View processing results
   - Monitor agent activity logs

### Stopping Access
Press `Ctrl+C` in the terminal to terminate the port forwarding session.

## Getting Deployment Information

Retrieve current deployment details from CloudFormation:

```bash
# Get all stack outputs
aws cloudformation describe-stacks --stack-name QualityInspectionStreamlitDemoStack --query 'Stacks[0].Outputs'

# Get specific values
aws cloudformation describe-stacks --stack-name QualityInspectionStreamlitDemoStack --query 'Stacks[0].Outputs[?OutputKey==`BastionInstanceId`].OutputValue' --output text
aws cloudformation describe-stacks --stack-name QualityInspectionStreamlitDemoStack --query 'Stacks[0].Outputs[?OutputKey==`StreamlitURL`].OutputValue' --output text
```

## Security Features

- No internet-facing endpoints
- Encrypted Session Manager tunneling
- Private subnet deployment
- VPC endpoint connectivity
- IAM-based access control