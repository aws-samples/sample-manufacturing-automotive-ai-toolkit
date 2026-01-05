# Fleet Discovery Platform

**Advanced AI-driven behavioral analysis system for autonomous vehicle development**

The Fleet Discovery Platform transforms raw ROS bag data into intelligent fleet insights through a sophisticated 6-phase pipeline that identifies statistically unique driving scenarios for model training optimization.

## Core Problem

Autonomous vehicle companies spend millions of dollars annually processing redundant fleet data, where 80-90% consists of routine scenarios already captured thousands of times. Our system uses AI to mathematically identify only the unique edge cases that matter for training.

## System Architecture

### Multi-Phase Intelligence Pipeline
- **Phase 1-2**: ROS bag extraction and video reconstruction with temporal synchronization
- **Phase 3**: InternVideo2.5 behavioral analysis + Cosmos-Embed1 visual pattern extraction
- **Phase 4-5**: Twin Engine embedding architecture (Cohere + Cosmos)
- **Phase 6**: Three-agent intelligence system for anomaly detection and business analysis

### Twin Engine Fleet Memory
- **Behavioral Engine**: Semantic concept matching (Cohere embed-v4, 1536-dim)
- **Visual Engine**: Temporal pattern recognition (Cosmos-Embed1, 768-dim)
- **Mathematical Consensus**: Cross-engine verification for high-confidence matches

## Key Features

- **Anti-Hallucination System**: Mathematical constraints prevent AI speculation beyond observed evidence
- **Real-time Dashboard**: Enterprise-grade web interface with transparent ROI calculations
- **Multi-Model Architecture**: Three S3 Vector indices for comprehensive behavioral coverage
- **Agent-Based Intelligence**: Computational agents with database access and statistical tools
- **Production-Ready Infrastructure**: AWS ECS, Lambda, Step Functions with zero-downtime deployment

## Business Impact

The objective is to enable intelligent discovery and extraction of high-value scenarios from Hardware-in-the-Loop (HIL) data, eliminating blind batch processing and reducing associated costs. 

Today, customers rely on operational metadata filtering, rule-based triggers, and manual labeling to identify relevant HIL data. Metadata filtering is too coarse to isolate specific scenarios. Rule-based triggers only capture events engineers anticipated (hard braking, collision warnings). Human labeling cannot scale with data volumes. Compounding this, customers cannot define edge cases they haven't yet encountered. These rare events emerge from complex visual interactions and cannot be anticipated or codified through predefined rules.

This creates unnecessary Data Transfer Out (DTO) costs from over-transferring low-value data, wasted compute on redundant scenarios, time-to-insight delays from manual curation bottlenecks, missed edge cases that don't match predefined rules, and an inability to answer questions like "do we have sufficient training data for this failure mode?" 

The proposed solution deploys AI-driven behavioral analysis to autonomously discover high-value scenarios—including undefined edge cases by detecting statistical anomalies and behavioral outliers across video data. The AI learns normal driving behavior and flags deviations, surfacing scenarios that would otherwise remain buried. For example, a pedestrian hesitating at a crosswalk in an unusual way that doesn't trigger any existing rule but represents a potential edge case for model training. 

Success is measured by selective data extraction that reduces DTO and compute costs, accelerated time-to-insight through automated scenario discovery, scalable analysis that grows with HIL test volumes, and the ability to identify training dataset gaps and support regulatory compliance searches. 

## Infrastructure

**AWS Services**: ECS, Lambda, S3, Step Functions, Bedrock, SageMaker
**Containers**: ARM64 (Graviton c7g) + x86_64 (Intel + NVIDIA A10G GPU) with auto-scaling
**Databases**: S3 Vectors multi-index architecture
**AI Models**: InternVideo2.5, Cosmos-Embed1, Cohere, Claude

## Quick Start

1. **Prerequisites**: AWS account with Bedrock access, Docker, CDK
2. **Deployment**: See `deployment-guide.md` for complete infrastructure setup
3. **Usage**: Access dashboard at configured App Runner endpoint
4. **Data Processing**: Upload ROS bags to trigger automatic pipeline execution

## Technical Highlights

- **Vector Mathematics**: Cosine similarity calculations in high-dimensional space
- **Temporal Synchronization**: Frame-perfect alignment across 6-camera arrays
- **Quantified Risk Assessment**: Mathematical constraints on behavioral scoring
- **Cross-Modal Search**: Text-to-video similarity via joint embedding space

## Documentation

- `deployment-guide.md` - Complete infrastructure deployment
- `PROJECT_STRUCTURE.md` - Codebase organization
- `EXECUTE_BACKFILL.md` - Data processing procedures

