# Fleet Discovery Platform - Project Structure

This document provides a comprehensive overview of the project's folder structure and file organization.

## Repository Overview

```
TESLA-PIPELINE-CONSOLIDATED/
├── README.md                                   # Project overview and quick start guide
├── .gitignore                                  # Git ignore rules for sensitive files
├── deployment-guide.md                         # Complete deployment instructions
├── PROJECT_STRUCTURE.md                        # This file - project organization guide
├── tesla_fleet_discovery_cdk_stack.py          # Main CDK infrastructure stack
├── app.py                                      # CDK app entry point
├── cdk.json                                    # CDK configuration
├── web_app.py                                  # Web stack app entry point
├── cloudfront_app.py                           # CloudFront stack app entry point
│
├── agents/                                     # AgentCore AI Agents (Bedrock)
├── pipeline/                                   # Core 6-Phase Processing Pipeline
├── infrastructure/                             # AWS CDK Infrastructure as Code
├── frontend/                                   # Next.js Web Application
├── web-api/                                    # App Runner Backend API
└── docs/                                      # Documentation and Examples
```

## Detailed Directory Structure

### `/agents/` - AgentCore AI Agents
**Purpose:** Bedrock AgentCore agents for Phase 6 multi-agent analysis

```
agents/
├── behavioral_gap_analysis_agent.py           # Analyzes behavioral patterns and gaps
├── intelligence_gathering_agent.py            # Gathers and correlates scene intelligence
├── safety_validation_agent.py                 # Validates safety scenarios and edge cases
├── s3_vectors_tools.py                        # S3 Vectors integration utilities
├── agentcore_behavioral_check.py              # AgentCore behavior validation utility
├── minimal_test_agent.py                      # Simple test agent for validation
├── requirements.txt                           # Agent-specific Python dependencies
├── .bedrock_agentcore.yaml                   # AgentCore deployment configuration
├── .dockerignore                              # Docker build exclusion rules
└── .bedrock_agentcore/                       # AgentCore deployment artifacts
```

**Deployment:** Uses AgentCore Toolkit (`agentcore deploy --agent [name] --auto-update-on-conflict`)
**AWS Resources:** 3 Bedrock AgentCore Runtime instances in us-west-2

### `/pipeline/` - Core Processing Pipeline
**Purpose:** 6-phase autonomous vehicle data processing pipeline

```
pipeline/
├── multi_sensor_rosbag_extractor.py           # Phase 1: ROS bag → structured data
├── rosbag_video_reconstructor.py              # Phase 2: Multi-camera video reconstruction
├── internvideo25_behavioral_analyzer.py       # Phase 3: InternVideo2.5 + Cosmos AI analysis
├── tesla_s3_vectors_behavioral_embeddings.py  # Phase 4-5: Multi-index behavioral embeddings
├── microservice_orchestrator.py               # Phase 6: Multi-agent coordination with Strands
├── create_dual_s3_vectors_indices.py          # S3 Vectors multi-index setup utility
├── s3_vectors_backfill_script.py             # Batch processing and backfill utility
└── requirements.txt                           # Pipeline Python dependencies
```

**Execution Flow:**
1. **Phase 1:** Extract sensor data from ROS bags
2. **Phase 2:** Reconstruct multi-camera videos
3. **Phase 3:** Generate AI behavioral analysis using InternVideo2.5
4. **Phase 4-5:** Create behavioral embeddings in S3 Vectors
5. **Phase 6:** Execute multi-agent analysis via AgentCore

**AWS Resources:** ECS Tasks orchestrated by Step Functions (`tesla-fleet-6phase-pipeline`)

### `/infrastructure/` - AWS CDK Infrastructure
**Purpose:** Infrastructure as Code for complete AWS deployment

```
infrastructure/
├── cloudfront_stack.py                        # Frontend CDN (TeslaCloudFrontStack - us-east-1)
├── web_stack.py                              # Web API (TeslaWebStack - us-west-2)
├── cloudfront_app.py                         # CloudFront stack app entry point
├── web_app.py                                # Web stack app entry point
├── inference.py                              # Inference utilities
├── cdk.json                                  # CDK framework configuration (copy)
├── Dockerfile                                # Main pipeline container (ARM64)
└── Dockerfile.phase3-fix                     # Phase 3 GPU container (AMD64)
```

**Note:** Main CDK stack (`tesla_fleet_discovery_cdk_stack.py`) is located in root directory due to deployment requirements.

**CDK Stacks:**
- **TeslaFleetProdStack (us-west-2):** ECS, Step Functions, Lambda, S3, SNS
- **TeslaWebStack (us-west-2):** App Runner, ECR, Custom Domain API
- **TeslaCloudFrontStack (us-east-1):** CloudFront, S3, ACM, Route 53

**Deployment:** `cdk deploy [StackName] --require-approval never --region [region]`

### Root Directory - CDK Deployment Files
**Purpose:** Primary CDK deployment files (copied from infrastructure/ for deployment requirements)

```
├── tesla_fleet_discovery_cdk_stack.py          # Main CDK infrastructure stack (TeslaFleetProdStack)
├── app.py                                      # CDK app entry point for main infrastructure
├── cdk.json                                    # CDK framework configuration
├── web_app.py                                  # Web stack CDK app entry point
├── cloudfront_app.py                           # CloudFront stack CDK app entry point
└── requirements.txt                            # Root CDK dependencies
```

**Note:** Due to CDK deployment requirements, main infrastructure files are in root directory with copies in `/infrastructure/` for organization.

### `/frontend/` - Tesla Discovery Studio Web App
**Purpose:** Next.js React application for fleet data visualization and analysis

```
frontend/
├── src/
│   ├── app/                                  # Next.js App Router (Pages)
│   │   ├── forensic/page.tsx                 # Scene forensic analysis interface
│   │   ├── analytics/page.tsx                # Analytics dashboard with metrics
│   │   ├── pipeline/page.tsx                 # Pipeline monitoring and status
│   │   ├── settings/page.tsx                 # System configuration panel
│   │   ├── layout.tsx                        # Main application layout wrapper
│   │   ├── page.tsx                          # Home/Landing page
│   │   └── not-found.tsx                     # 404 error page handler
│   │
│   ├── components/                           # Reusable React Components
│   │   ├── ui/                              # Basic UI primitives (buttons, cards, etc.)
│   │   ├── auth/                            # Authentication components
│   │   └── dashboard/                       # Dashboard-specific widgets
│   │
│   └── types/                               # TypeScript Type Definitions
│       └── scene.ts                         # Scene data structure types
│
├── public/                                  # Static Assets (images, icons, etc.)
├── next.config.ts                           # Next.js build configuration
├── package.json                             # Node.js dependencies and scripts
├── tailwind.config.js                       # Tailwind CSS styling configuration
└── tsconfig.json                            # TypeScript compiler configuration
```

**Key Features:**
- **Static Export:** Configured for CloudFront deployment (`output: 'export'`)
- **Direct URL Navigation:** Supports deep linking to specific scenes
- **Responsive Design:** Mobile and desktop optimized interfaces
- **Real-time Data:** Connects to backend API for live pipeline status

**Deployment:** Built via `npm run build`, deployed via CDK to CloudFront + S3

### `/web-api/` - Backend API Service
**Purpose:** App Runner service providing REST API for frontend and external integrations

```
web-api/
├── dashboard_api.py                          # Main FastAPI application with endpoints
├── app_runner.py                            # App Runner service entry point
├── requirements.txt                         # Python API dependencies
└── Dockerfile                               # Container image (AMD64 for App Runner)
```

**API Endpoints:**
- `/health` - Service health check
- `/api/scenes` - Scene listing and metadata
- `/api/pipeline/status` - Pipeline execution status
- `/api/analytics/*` - Analytics data endpoints

**Deployment:** Container deployed to App Runner with custom domain (`api.auto-mfg-pvt-ltd.co`)

### `/docs/` - Documentation and Examples
**Purpose:** Project documentation, examples, and sample data

```
docs/
├── sample-outputs/                           # Example processing results
│   └── scene-0017/                         # Sample scene processing pipeline
│       ├── phase1/                         # ROS bag extraction JSON output
│       ├── phase2/                         # Multi-camera MP4 video files
│       ├── phase3/                         # InternVideo2.5 AI analysis results
│       ├── phase4-5/                       # S3 Vectors behavioral embeddings
│       └── phase6/                         # Multi-agent analysis insights
│
└── architecture-overview.md                 # System architecture documentation
```

**Sample Data Purpose:**
- **Development Reference:** Example of expected data formats
- **Testing:** Known good outputs for validation
- **Documentation:** Illustrates complete pipeline flow

## File Naming Conventions

### Original Names Preserved
All core pipeline files maintain their original names for consistency:
- `multi_sensor_rosbag_extractor.py` (not `phase1_extractor.py`)
- `rosbag_video_reconstructor.py` (not `phase2_video.py`)
- `internvideo25_behavioral_analyzer.py` (not `phase3_analyzer.py`)

### Agent Files
Agent files follow AgentCore naming conventions:
- `[purpose]_agent.py` format
- Snake_case naming for Python compatibility
- Descriptive names indicating function

### Infrastructure Files
CDK files use descriptive stack names:
- `tesla_fleet_discovery_cdk_stack.py` (main infrastructure)
- `cloudfront_stack.py` (frontend CDN)
- `web_stack.py` (API services)

## AWS Resource Mapping

### US-West-2 (Main Region)
```
infrastructure/tesla_fleet_discovery_cdk_stack.py → TeslaFleetProdStack
├── ECS Clusters: tesla-fleet-cpu-cluster-<unique-id>, tesla-fleet-gpu-cluster
├── Step Functions: tesla-fleet-6phase-pipeline
├── Lambda: tesla-s3-trigger-us-west-2
├── S3: tesla-fleet-discovery-<unique-id>, tesla-fleet-vectors-<unique-id>
└── SNS: vehicle-fleet-pipeline-success, tesla-fleet-critical-failures

infrastructure/web_stack.py → TeslaWebStack
├── App Runner: tesla-fleet-api
├── ECR: tesla-web-api
└── Custom Domain: api.auto-mfg-pvt-ltd.co

agents/* → Bedrock AgentCore
├── behavioral_gap_analysis_agent-[ID]
├── intelligence_gathering_agent-[ID]
└── safety_validation_agent-[ID]
```

### US-East-1 (CDN Region)
```
infrastructure/cloudfront_stack.py → TeslaCloudFrontStack
├── CloudFront: Distribution with auto-mfg-pvt-ltd.co
├── S3: tesla-frontend-auto-mfg-pvt-ltd-co-757513153970
├── ACM: SSL certificate for HTTPS
└── Route 53: DNS records for custom domain
```

## Development Workflow

### 1. Local Development
```bash
# Pipeline development
cd pipeline/
python multi_sensor_rosbag_extractor.py

# Frontend development
cd frontend/
npm run dev

# API development
cd web-api/
python dashboard_api.py
```

### 2. Agent Development
```bash
cd agents/
source ~/.local/pipx/venvs/bedrock-agentcore-starter-toolkit/bin/activate
agentcore deploy --agent [agent-name] --auto-update-on-conflict
```

### 3. Infrastructure Updates
```bash
cd infrastructure/
source cdk-env/bin/activate
cdk deploy [StackName] --require-approval never --region [region]
```

### 4. Container Updates
```bash
# Pipeline images (ARM64)
docker build --platform=linux/arm64 -t vehicle-fleet-pipeline .

# Web API images (AMD64 - Critical for App Runner)
docker build --platform=linux/amd64 -t tesla-web-api .
```

## Pipeline Trigger Configuration

**S3 Trigger Path:** `s3://tesla-fleet-discovery-<unique-id>/raw-data/tesla-pipeline/`

**Process:**
1. Upload ROS bag to trigger path
2. Lambda `tesla-s3-trigger-us-west-2` detects upload
3. Step Functions `tesla-fleet-6phase-pipeline` starts execution
4. ECS tasks process through phases 1-6
5. Results stored in S3 and S3 Vectors

## Key Architecture Decisions

### Why This Structure?
1. **Separation of Concerns:** Each directory has a single, clear responsibility
2. **Deployment Isolation:** Components can be updated independently
3. **Original Names:** Maintains consistency with existing documentation
4. **AWS Region Split:** Optimizes for global CDN delivery and compute locality
5. **Latest Files:** Uses most recent versions from active development

### Container Architecture Strategy
- **ARM64 for ECS:** Cost-effective compute for CPU-intensive pipeline tasks
- **AMD64 for App Runner:** Required for App Runner health checks and compatibility
- **Multi-platform builds:** Explicit platform specification prevents deployment failures

This structure enables efficient development, deployment, and maintenance of the complete Tesla Fleet Discovery Platform while preserving the existing codebase investment and optimizing for AWS best practices.

---

**Last Updated:** December 2025
**Maintained By:** Tesla Fleet Discovery Team