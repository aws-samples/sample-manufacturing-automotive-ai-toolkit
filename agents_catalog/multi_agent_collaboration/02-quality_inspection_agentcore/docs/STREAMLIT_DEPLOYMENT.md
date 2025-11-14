# Streamlit Local Deployment Guide

## Overview
The Streamlit application provides a web interface for testing and demonstrating the quality inspection multi-agent system. It runs locally and connects to your deployed AWS infrastructure.

## Prerequisites
- Python 3.10+
- AWS CLI configured with credentials
- CDK infrastructure deployed (`cd infrastructure && cdk deploy`)

## Quick Start

### 1. Run the Application
```bash
./run_streamlit.sh
```

### 2. Access the Interface
- Open browser to: http://localhost:8501
- The application will auto-detect your AWS account and S3 bucket

## Features

### 🔍 Image Processing
- Upload images to S3 `inputimages/` folder
- Automatic AgentCore workflow triggering
- Real-time processing status

### 🤖 AgentCore Integration
- Connects to deployed AgentCore agents in private VPC
- Displays agent status and execution logs
- Shows processing results from DynamoDB

### 📊 Results Visualization
- Defect detection with bounding boxes
- SOP compliance decisions
- Processing history and trends
- Agent communication logs

## Configuration

### Environment Variables
```bash
export AWS_DEFAULT_REGION=us-east-1
export STREAMLIT_SERVER_PORT=8501
```

### AWS Resources Required
- S3 bucket: `machinepartimages-{account-id}`
- DynamoDB table: `vision-inspection-data`
- AgentCore agents deployed and running
- CloudWatch logs access

## Troubleshooting

### Common Issues

1. **AWS Credentials Not Found**
   ```bash
   aws configure
   # or
   export AWS_PROFILE=your-profile
   ```

2. **S3 Bucket Not Found**
   ```bash
   cd infrastructure
   cdk deploy
   ```

3. **No Processing Results**
   - Check AgentCore agents are deployed
   - Verify S3 trigger Lambda is working
   - Check CloudWatch logs

4. **Permission Denied**
   ```bash
   chmod +x run_streamlit.sh
   ```

### Debug Mode
```bash
# Run with debug logging
STREAMLIT_LOGGER_LEVEL=debug ./run_streamlit.sh
```

## Development

### Local Testing
```bash
# Install dependencies
pip install -r requirements.txt

# Run directly
cd src
streamlit run quality-inspection-streamlit-demo.py
```

### Adding Features
- Modify `src/quality-inspection-streamlit-demo.py`
- Add new dependencies to `requirements.txt`
- Test with `./run_streamlit.sh`

## Architecture

```
Local Machine          AWS Cloud
┌─────────────────┐    ┌──────────────────┐
│ Streamlit App   │────│ S3 Bucket        │
│ (Port 8501)     │    │ DynamoDB Tables  │
│                 │    │ AgentCore Agents │
│ - Upload Images │    │ CloudWatch Logs  │
│ - View Results  │    │ SNS Notifications│
│ - Monitor Logs  │    └──────────────────┘
└─────────────────┘
```

## Security Notes
- Application runs locally with your AWS credentials
- No cloud hosting or public access
- Uses existing IAM permissions for AWS resource access
- Suitable for demos, testing, and development only