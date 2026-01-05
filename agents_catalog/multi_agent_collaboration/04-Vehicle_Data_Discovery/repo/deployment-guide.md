# Fleet Discovery Platform - Deployment Guide

Complete deployment instructions for the Fleet Discovery Platform HIL scenario discovery system.

## Prerequisites

### Required Tools
```bash
# AWS CLI v2
aws --version

# AWS CDK v2
npm install -g aws-cdk
cdk --version

# Docker Desktop (running)
docker --version

# Node.js 18+
node --version
npm --version

# Python 3.9+
python3 --version

# AgentCore Toolkit
pipx install bedrock-agentcore-starter-toolkit
```

### AWS Configuration
```bash
# Configure AWS credentials
aws configure

# Verify access to your account (should show account: 757513153970)
aws sts get-caller-identity
```

## Phase 1: Infrastructure Deployment (CDK)

### 1.1 Setup CDK Environment
```bash
cd /path/to/fleet-discovery-platform

# Create and activate Python virtual environment for CDK
python3 -m venv cdk-env
source cdk-env/bin/activate

# Install CDK dependencies
pip install aws-cdk-lib constructs boto3 aws-cdk.aws-s3-deployment

# Bootstrap CDK (first time only per region)
cdk bootstrap --region us-west-2
cdk bootstrap --region us-east-1
```

### 1.2 Deploy Main Infrastructure (US-West-2)
```bash
# Copy CDK files to root (required after repository reorganization)
# Check if files exist, copy if needed
ls -la app.py cdk.json tesla_fleet_discovery_cdk_stack.py 2>/dev/null || {
    echo "Copying CDK files from infrastructure/ directory..."
    cp infrastructure/tesla_fleet_discovery_cdk_stack.py .
    cp infrastructure/cdk.json .
    echo "CDK files copied successfully."
}

# Ensure CDK environment is active
source cdk-env/bin/activate

# Deploy main Tesla Fleet infrastructure (US-West-2)
# Creates: ECS Clusters, Step Functions, Lambda, S3, SNS, AgentCore integration
cdk deploy TeslaFleetProdStack --require-approval never --region us-west-2

# Save outputs for reference
cdk deploy TeslaFleetProdStack --require-approval never --region us-west-2 --outputs-file cdk-outputs-main.json
```

**Expected Resources Created:**
- ECS Clusters: `tesla-fleet-cpu-cluster-<unique-id>`, `tesla-fleet-gpu-cluster`
- Step Functions: `tesla-fleet-6phase-pipeline` (main orchestrator)
- Lambda: `tesla-s3-trigger-us-west-2` (pipeline trigger)
- S3 Buckets: `tesla-fleet-discovery-<unique-id>`, `tesla-fleet-vectors-<unique-id>`
- SNS Topics: `vehicle-fleet-pipeline-success`, `tesla-fleet-critical-failures`
- ECS Task Definitions: tesla-phase1-extraction, tesla-phase2-video, tesla-phase3-internvideo25-gpu, tesla-phase45-embeddings, tesla-phase6-orchestrator

### 1.3 Deploy Web API Stack (US-West-2)
```bash
# Build and prepare Web API image with correct AMD64 architecture for App Runner
# IMPORTANT: Web API code is located in /web-api/ directory (not web-deployment/api/)
cd web-api/
docker build --platform=linux/amd64 -t tesla-web-api .
docker tag tesla-web-api:latest 757513153970.dkr.ecr.us-west-2.amazonaws.com/tesla-web-api:latest

# Login to ECR and push image
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 757513153970.dkr.ecr.us-west-2.amazonaws.com
docker push 757513153970.dkr.ecr.us-west-2.amazonaws.com/tesla-web-api:latest

# Deploy App Runner web API (api.auto-mfg-pvt-ltd.co)
# This automatically triggers App Runner to pull and deploy the latest ECR image
cd ../
source cdk-env/bin/activate
cdk deploy TeslaWebStack --require-approval never --region us-west-2
```

**Expected Resources Created:**
- App Runner Service: `tesla-fleet-api` (6kicn2wbzm.us-west-2.awsapprunner.com)
- Custom Domain: api.auto-mfg-pvt-ltd.co
- ECR Repository: tesla-web-api

**Important:** App Runner has auto-deployments enabled and will automatically detect and deploy new ECR images within 2-3 minutes. No manual CDK deployment or service update is needed after ECR push.

**Note:** If auto-deployment fails, you can manually trigger deployment using CDK:
```bash
cd ../
source cdk-env/bin/activate
cdk deploy TeslaWebStack --require-approval never --region us-west-2
```

### 1.4 Deploy CloudFront CDN Stack (US-East-1)
```bash
# Build frontend with correct architecture for CDK deployment
cd frontend/
npm install
npm run build

# Deploy CloudFront distribution for frontend (US-East-1)
# IMPORTANT: CloudFront uses a separate app file (cloudfront_app.py)
cd ../
source cdk-env/bin/activate
cdk deploy TeslaCloudFrontStack --app "python3 cloudfront_app.py" --require-approval never --region us-east-1
```

**Expected Resources Created:**
- CloudFront Distribution with custom domain (auto-mfg-pvt-ltd.co)
- S3 Bucket: tesla-frontend-auto-mfg-pvt-ltd-co-757513153970
- ACM SSL Certificate for HTTPS
- Route 53 DNS records
- CloudFront Function for directory index handling

### 1.5 Deploy Cosmos-Embed1 SageMaker Endpoint (Optional - for Real-Time Search)
```bash
# IMPORTANT: This step is OPTIONAL but recommended for production search performance
# Currently, Cosmos embeddings are generated during pipeline processing (Phase 3)
# This endpoint enables real-time Cosmos text embeddings for search queries

# Deploy Cosmos-Embed1 SageMaker endpoint for real-time visual search
# Note: This requires significant GPU resources (ml.g4dn.xlarge or larger)
cd cosmos-sagemaker-deployment/

# Build and deploy Cosmos endpoint (if cosmos-sagemaker-deployment/ exists)
# ./deploy-cosmos-endpoint.sh

echo "WARNING: SageMaker Cosmos endpoint deployment is currently MANUAL"
echo "Backend is configured for endpoint: 'endpoint-cosmos-embed1-text'"
echo "If endpoint not deployed, visual search will be disabled"
echo "Pipeline will continue using local GPU Cosmos processing"
```

**Expected Resources (If Deployed):**
- SageMaker Endpoint: `endpoint-cosmos-embed1-text`
- SageMaker Model: `nvidia/Cosmos-Embed1-448p`
- Instance Type: `ml.g4dn.xlarge` (minimum for Cosmos)
- Auto-scaling: 1-3 instances based on load

**Current Status**:
- WORKING: Pipeline Processing - Cosmos works locally in Phase 3 containers
- PENDING: Real-Time Search - Requires manual SageMaker endpoint deployment
- FALLBACK: Search will use Cohere-only if endpoint unavailable

## Phase 2: AgentCore Agent Deployment

### 2.1 Setup AgentCore Environment
```bash
# Activate the AgentCore virtual environment
source ~/.local/pipx/venvs/bedrock-agentcore-starter-toolkit/bin/activate

# Navigate to the directory containing updated agent files
cd agents/
```

### 2.2 Deploy Individual Agents
```bash
# Configure agents with container deployment (one-time setup)
agentcore configure --entrypoint behavioral_gap_analysis_agent.py --name behavioral_gap_analysis_agent --deployment-type container --non-interactive
agentcore configure --entrypoint intelligence_gathering_agent.py --name intelligence_gathering_agent --deployment-type container --non-interactive
agentcore configure --entrypoint safety_validation_agent.py --name safety_validation_agent --deployment-type container --non-interactive

# Deploy agents using container deployment
agentcore deploy --agent behavioral_gap_analysis_agent
agentcore deploy --agent intelligence_gathering_agent
agentcore deploy --agent safety_validation_agent
```

**Expected AgentCore Runtimes:**
- behavioral_gap_analysis_agent-[ID] (arn:aws:bedrock-agentcore:us-west-2:757513153970:runtime/...)
- intelligence_gathering_agent-[ID]
- safety_validation_agent-[ID]

### 2.3 Verify Agent Deployment
```bash
# List deployed agents
agentcore list

# Check agent status
agentcore status --agent behavioral_gap_analysis_agent
agentcore status --agent intelligence_gathering_agent
agentcore status --agent safety_validation_agent

# Note: Agent ARNs will be different after container deployment
# Update your pipeline code with the new ARNs shown in deployment output
```

### 2.4 Update Pipeline ARNs
After deploying agents with container deployment, update the hardcoded ARNs in your pipeline:

```python
# Update these ARNs in your microservice_orchestrator.py
AGENT_RUNTIME_ARNS = {
    "scene_understanding": "arn:aws:bedrock-agentcore:us-west-2:757513153970:runtime/behavioral_gap_analysis_agent-[NEW_ID]",
    "anomaly_detection": "arn:aws:bedrock-agentcore:us-west-2:757513153970:runtime/safety_validation_agent-[NEW_ID]", 
    "similarity_search": "arn:aws:bedrock-agentcore:us-west-2:757513153970:runtime/intelligence_gathering_agent-[NEW_ID]"
}
```

**Current Working ARNs (as of Dec 13, 2025):**
```python
AGENT_RUNTIME_ARNS = {
    "scene_understanding": "arn:aws:bedrock-agentcore:us-west-2:757513153970:runtime/behavioral_gap_analysis_agent-k0RUD0DWaw",
    "anomaly_detection": "arn:aws:bedrock-agentcore:us-west-2:757513153970:runtime/safety_validation_agent-78fqtDCeQ2",
    "similarity_search": "arn:aws:bedrock-agentcore:us-west-2:757513153970:runtime/intelligence_gathering_agent-UX77aUGW5H"
}
```

## Phase 3: Pipeline Container Images Deployment

### 3.1 Build and Push Main Pipeline Image (ARM64)
```bash
# Build main pipeline image for phases 1,2,4,5,6 (ARM64 for ECS)
docker build --platform=linux/arm64 -t vehicle-fleet-pipeline .

# Tag for ECR
docker tag vehicle-fleet-pipeline:latest 757513153970.dkr.ecr.us-west-2.amazonaws.com/vehicle-fleet-pipeline:latest

# Login to ECR
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 757513153970.dkr.ecr.us-west-2.amazonaws.com

# Push to ECR
docker push 757513153970.dkr.ecr.us-west-2.amazonaws.com/vehicle-fleet-pipeline:latest
```

### 3.2 Build and Push Phase 3 GPU Image (AMD64)
```bash
# Build Phase 3 InternVideo2.5 GPU image (AMD64)
docker build --platform=linux/amd64 -f Dockerfile.phase3-fix -t tesla-phase3-internvideo .
docker tag tesla-phase3-internvideo:latest 757513153970.dkr.ecr.us-west-2.amazonaws.com/vehicle-fleet-pipeline:v-phase3-gpu-amd64
docker push 757513153970.dkr.ecr.us-west-2.amazonaws.com/vehicle-fleet-pipeline:v-phase3-gpu-amd64
```

### 3.3 Update ECS Task Definitions
```bash
# Copy CDK files to root (required after repository reorganization)
cp infrastructure/tesla_fleet_discovery_cdk_stack.py .
cp infrastructure/cdk.json .

# Activate CDK environment
source cdk-env/bin/activate

# Update task definitions with new images
cdk deploy TeslaFleetProdStack --require-approval never --region us-west-2
```

**Note:** Due to repository reorganization, CDK files are stored in `infrastructure/` but deployment requires them in root directory. The copy commands above handle this automatically.

## Phase 4: Testing Deployment

### 4.1 Verify Infrastructure
```bash
# Check Step Functions
aws stepfunctions list-state-machines --region us-west-2

# Check ECS clusters
aws ecs describe-clusters --clusters tesla-fleet-cpu-cluster-<unique-id> --region us-west-2

# Check App Runner service
aws apprunner describe-services --service-arn arn:aws:apprunner:us-west-2:757513153970:service/tesla-fleet-api/8d1e4df44f58414dab740df3e664ca9c

# Check AgentCore runtimes
source ~/.local/pipx/venvs/bedrock-agentcore-starter-toolkit/bin/activate
agentcore list
```

### 4.2 Test Frontend
```bash
# Test direct URL navigation (CloudFront Function working)
curl -s "https://auto-mfg-pvt-ltd.co/forensic/?id=scene-0011" | grep -o "71fcce0e0a920aaa"
# Should return: 71fcce0e0a920aaa (forensic page marker)

# Test home page
curl -s "https://auto-mfg-pvt-ltd.co/" | grep -o "Tesla Fleet Discovery"
```

### 4.3 Test Backend API
```bash
# Test API health endpoint
curl "https://api.auto-mfg-pvt-ltd.co/health"

# Test scene listing
curl "https://api.auto-mfg-pvt-ltd.co/api/scenes"

# Test App Runner direct URL
curl "https://6kicn2wbzm.us-west-2.awsapprunner.com/health"
```

### 4.4 Test Pipeline Trigger
**IMPORTANT: Pipeline Trigger Path Configuration**

The pipeline is automatically triggered when ROS bag files are uploaded to the specific S3 path:

**S3 Bucket:** `tesla-fleet-discovery-<unique-id>`
**Trigger Path Prefix:** `raw-data/tesla-pipeline/`

**To trigger the pipeline, upload actual ROS bag files to:**
```bash
# Upload actual ROS bag file (replace with your actual .bag file)
aws s3 cp your-actual-scene.bag s3://tesla-fleet-discovery-<unique-id>/raw-data/tesla-pipeline/your-actual-scene.bag

# The Lambda function tesla-s3-trigger-us-west-2 will automatically detect the upload
# and start the Step Functions pipeline: tesla-fleet-6phase-pipeline
```

**Check pipeline execution:**
```bash
# Check Step Functions execution
aws stepfunctions list-executions --state-machine-arn arn:aws:states:us-west-2:757513153970:stateMachine:tesla-fleet-6phase-pipeline --region us-west-2

# Check most recent execution status
aws stepfunctions list-executions --state-machine-arn arn:aws:states:us-west-2:757513153970:stateMachine:tesla-fleet-6phase-pipeline --max-items 1 --region us-west-2
```

**Note:** Do not create test/dummy bag files. Use actual ROS bag files from your Tesla fleet data for proper pipeline testing.

## Configuration & Monitoring

### Environment Variables
Key environment variables in App Runner Service (`tesla-fleet-api`):

- `AWS_REGION=us-west-2`
- `S3_BUCKET_NAME=tesla-fleet-discovery-<unique-id>`
- `STATE_MACHINE_ARN=arn:aws:states:us-west-2:757513153970:stateMachine:tesla-fleet-6phase-pipeline`

### Monitoring & Logs
```bash
# View Step Functions logs
aws logs tail /aws/tesla-fleet-discovery-studio --follow --region us-west-2

# View Lambda trigger logs
aws logs tail /aws/lambda/tesla-s3-trigger-us-west-2 --follow --region us-west-2

# View App Runner logs
aws logs tail /aws/apprunner/tesla-fleet-api --follow --region us-west-2

# View AgentCore agent logs
source ~/.local/pipx/venvs/bedrock-agentcore-starter-toolkit/bin/activate
agentcore logs --agent behavioral_gap_analysis_agent
```

## Troubleshooting Common Issues

### Issue 1: CDK Deploy Permission Errors
**Symptom:** CDK deploy fails with permission denied

**Solution:**
```bash
# Verify AWS credentials and account
aws sts get-caller-identity
# Should show account: 757513153970

# Verify region settings
aws configure get region
# Should show us-west-2 for main stack, us-east-1 for CloudFront
```

### Issue 2: Docker Architecture Mismatch
**Symptom:** ECS tasks fail with exec format error OR App Runner health checks fail

**Solution:**
```bash
# Use correct platform for each image type:

# Main pipeline (ECS ARM64):
docker build --platform=linux/arm64 -t vehicle-fleet-pipeline .

# Phase 3 GPU (ECS AMD64):
docker build --platform=linux/amd64 -f Dockerfile.phase3-fix -t vehicle-phase3-internvideo .

# Web API (App Runner AMD64 - CRITICAL):
docker build --platform=linux/amd64 -t vehicle-web-api .
```

**IMPORTANT:** If you don't specify `--platform=linux/amd64` when building the Web API image for App Runner, the service will fail health checks on port 8000.

### Issue 3: App Runner Health Check Failures
**Symptom:** App Runner deployment fails at health check stage

**Root Cause:** Web API Docker image built without correct AMD64 architecture

**Solution:**
```bash
cd web-api/
# Rebuild with correct architecture
docker build --platform=linux/amd64 -t tesla-web-api .
docker tag tesla-web-api:latest 757513153970.dkr.ecr.us-west-2.amazonaws.com/tesla-web-api:latest
docker push 757513153970.dkr.ecr.us-west-2.amazonaws.com/tesla-web-api:latest

# Redeploy Web Stack to trigger App Runner update
cd ../
source cdk-env/bin/activate
cdk deploy TeslaWebStack --require-approval never --region us-west-2
```

### Issue 4: AgentCore Deployment Fails
**Symptom:** `agentcore deploy` returns errors

**Solution:**
```bash
# Verify AgentCore environment
source ~/.local/pipx/venvs/bedrock-agentcore-starter-toolkit/bin/activate
agentcore --version

# Check agent configuration
cat .bedrock_agentcore.yaml

# Verify from correct directory (should contain agent .py files)
ls -la behavioral_gap_analysis_agent.py intelligence_gathering_agent.py safety_validation_agent.py
```

### Issue 5: Step Functions Pipeline Not Triggered
**Symptom:** ROS bag upload doesn't trigger pipeline

**Solution:**
```bash
# Verify correct S3 upload path
# MUST use: s3://tesla-fleet-discovery-<unique-id>/raw-data/tesla-pipeline/

# Check Lambda function status
aws lambda get-function --function-name tesla-s3-trigger-us-west-2 --region us-west-2

# Check S3 event notifications are configured
aws s3api get-bucket-notification-configuration --bucket tesla-fleet-discovery-<unique-id>

# Manual pipeline test (if needed)
aws stepfunctions start-execution \
    --state-machine-arn arn:aws:states:us-west-2:757513153970:stateMachine:tesla-fleet-6phase-pipeline \
    --input '{"scene_id":"test-001","input_rosbag_key":"raw-data/tesla-pipeline/test-scene.bag"}' \
    --region us-west-2
```

## Update Procedures

### Updating Frontend:
```bash
cd frontend/
npm run build
cd ../
source cdk-env/bin/activate
# Note: CloudFront uses cloudfront_app.py, not app.py
cdk deploy TeslaCloudFrontStack --app "python3 cloudfront_app.py" --require-approval never --region us-east-1

# Clear CloudFront cache
aws cloudfront create-invalidation --distribution-id [DISTRIBUTION_ID] --paths "/*"
```

### Updating Pipeline Images:
```bash
# Rebuild and push updated images
docker build --platform=linux/arm64 -t vehicle-fleet-pipeline .
docker push 757513153970.dkr.ecr.us-west-2.amazonaws.com/vehicle-fleet-pipeline:latest

# Update ECS task definitions
source cdk-env/bin/activate
cdk deploy TeslaFleetProdStack --require-approval never --region us-west-2
```

### Updating Web API:
```bash
cd web-api/
# CRITICAL: Use AMD64 architecture for App Runner
docker build --platform=linux/amd64 -t tesla-web-api .
docker push 757513153970.dkr.ecr.us-west-2.amazonaws.com/tesla-web-api:latest

# CDK deployment automatically triggers App Runner update
cd ../
source cdk-env/bin/activate
cdk deploy TeslaWebStack --require-approval never --region us-west-2
```

### Updating Agents:
```bash
source ~/.local/pipx/venvs/bedrock-agentcore-starter-toolkit/bin/activate
cd agents/
# For container deployment, simply redeploy with updated code
agentcore deploy --agent [agent-name] --auto-update-on-conflict
```

**Note:** Container deployment automatically rebuilds the Docker image with your updated code and maintains the same agent ARN.

### Updating Infrastructure:
```bash
# Copy CDK files to root (required after repository reorganization)
cp infrastructure/tesla_fleet_discovery_cdk_stack.py .
cp infrastructure/cdk.json .
cp infrastructure/web_stack.py .
cp infrastructure/cloudfront_stack.py .

# Activate CDK environment
source cdk-env/bin/activate

# Update main infrastructure
cdk deploy TeslaFleetProdStack --require-approval never --region us-west-2

# Update web API infrastructure
cdk deploy TeslaWebStack --require-approval never --region us-west-2

# Update CloudFront infrastructure (requires cloudfront_app.py)
cdk deploy TeslaCloudFrontStack --app "python3 cloudfront_app.py" --require-approval never --region us-east-1
```

## Stack Summary

| Stack | Region | Purpose | Key Resources |
|-------|---------|---------|---------------|
| **TeslaFleetProdStack** | us-west-2 | Main pipeline | Step Functions, ECS, Lambda, S3, SNS |
| **TeslaWebStack** | us-west-2 | Web API | App Runner, ECR, Custom Domain |
| **TeslaCloudFrontStack** | us-east-1 | Frontend CDN | CloudFront, S3, ACM, Route 53 |

## CDK App File Reference

**IMPORTANT:** Different stacks use different CDK app files. Using the wrong app file will result in "stack not found" errors.

| Stack | CDK App File | Usage |
|-------|--------------|-------|
| **TeslaFleetProdStack** | `app.py` | Main pipeline infrastructure |
| **TeslaWebStack** | `app.py` | Web API deployment |
| **TeslaCloudFrontStack** | `cloudfront_app.py` | Frontend CDN (separate app required) |

**Deploy Commands:**
```bash
# Main infrastructure and Web API
cdk deploy TeslaFleetProdStack --require-approval never --region us-west-2
cdk deploy TeslaWebStack --require-approval never --region us-west-2

# CloudFront (requires separate app file)
cdk deploy TeslaCloudFrontStack --app "python3 cloudfront_app.py" --require-approval never --region us-east-1
```

## Cosmos-Embed1 Integration Architecture

### Multi-Modal Embedding System Overview

The Tesla Fleet Discovery Platform uses a sophisticated **dual-embedding architecture** combining behavioral analysis (Cohere) with visual pattern recognition (Cosmos):

**Architecture Components:**

| Component | Technology | Purpose | Deployment Status |
|-----------|------------|---------|-------------------|
| **Behavioral Analysis** | Cohere embed-v4 (1536-dim) | Semantic concept matching | DEPLOYED (Bedrock) |
| **Visual Pattern Analysis** | Cosmos-Embed1-448p (768-dim) | Temporal video understanding | PARTIAL (Local GPU) |
| **Storage Layer** | S3 Vectors (dual-index) | Multi-modal similarity search | DEPLOYED |
| **Real-Time Search** | SageMaker Endpoint | Live visual embedding | MANUAL SETUP REQUIRED |

### Cosmos Integration Points

**1. Pipeline Processing (Phase 3 - WORKING)**
```bash
# Phase 3 Container: Local GPU Cosmos processing
internvideo25_behavioral_analyzer.py → cosmos_embed_video() → 768-dim embeddings
```

**2. S3 Vectors Storage (Phase 4-5 - WORKING)**
```bash
# Multi-index storage architecture
behavioral-metadata-index: Cohere embeddings (concept matching)
video-similarity-index: Cosmos embeddings (visual pattern matching)
```

**3. Real-Time Search (Web API - REQUIRES SAGEMAKER ENDPOINT)**
```bash
# Backend configuration ready, endpoint deployment pending
dashboard_api.py → sagemaker.invoke_endpoint("endpoint-cosmos-embed1-text")
```

### Deployment Status Summary

**DEPLOYED & WORKING:**
- Cosmos model loading in Phase 3 ECS containers (GPU-enabled)
- Video embedding generation during pipeline processing
- S3 Vectors storage in `video-similarity-index`
- Twin Engine search architecture (Cohere + Cosmos results)

**PENDING MANUAL DEPLOYMENT:**
- SageMaker Endpoint: `endpoint-cosmos-embed1-text`
- Real-time Cosmos text embedding for search queries
- Auto-scaling SageMaker configuration

**CURRENT BEHAVIOR:**
- Pipeline: Full Cosmos integration working
- Search: Falls back to Cohere-only if SageMaker endpoint unavailable
- Frontend: Displays "visual" engine in Twin Engine results when Cosmos data available

### SageMaker Endpoint Configuration (Manual Setup Required)

**Resource Requirements:**
- Instance: `ml.g4dn.xlarge` (minimum) or `ml.g4dn.2xlarge` (recommended)
- GPU Memory: 16GB+ for Cosmos-Embed1-448p model
- Endpoint Name: `endpoint-cosmos-embed1-text` (hardcoded in backend)

**Payload Format:**
```json
{
  "inputs": ["construction zone with orange barriers"]
}
```

**Response Format:**
```json
[
  [0.1234, -0.5678, 0.9101, ...] // 768-dimensional embedding
]
```

## Critical S3 Path Configuration

**Pipeline Trigger Path:** Users must upload ROS bag files to this exact S3 path for automatic pipeline execution:

```
s3://tesla-fleet-discovery-<unique-id>/raw-data/tesla-pipeline/[your-rosbag-file].bag
```

The Lambda function `tesla-s3-trigger-us-west-2` monitors this specific prefix and automatically starts the Step Functions pipeline when new ROS bags are detected.

