# SFC Config Generation Agent

Accelerate Industrial Equipment Onboarding by creating, validating, and running **Shop Floor Connectivity (SFC)** configurations using AI.

## Overview

This agent leverages Amazon Bedrock (Claude) and the Strands Agents SDK to assist with SFC configuration tasks. It exposes an MCP server (`sfc-spec-mcp-server.py`) as its primary knowledge source for validation and combines it with internal tools for file operations, conversation logging, and configuration analysis.

## Key Capabilities

- **Create** new SFC configuration JSON files from natural-language descriptions
- **Validate** existing configurations against the SFC specification (via MCP tools)
- **Read / Save** configurations and results to cloud storage (S3 + DynamoDB)
- **Analyze** SFC modules and visualize data

## Project Structure

```
01-sfc-config-agent/
├── manifest.json            # Agent metadata & CDK infrastructure definition
├── requirements.txt         # Python dependencies
├── cdk/                     # CDK stack for deploying the agent infrastructure
└── src/
    ├── agent.py             # Main agent entry-point (AgentCore runtime)
    ├── sfc-spec-mcp-server.py  # MCP server exposing SFC spec tools
    ├── sfc-config-example.json # Example SFC configuration
    └── tools/               # Internal agent tools
        ├── data_visualizer.py
        ├── file_operations.py
        ├── prompt_logger.py
        ├── sfc_knowledge.py
        └── sfc_module_analyzer.py
```

## Prerequisites

- Python 3.11+
- AWS credentials with Amazon Bedrock access
- Model access enabled for the configured model (default: `us.anthropic.claude-sonnet-4-20250514-v1:0`)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Optional: configure via .env
export BEDROCK_MODEL_ID="us.anthropic.claude-sonnet-4-20250514-v1:0"
export BEDROCK_REGION="us-east-1"

# Run the agent (exposes AgentCore API on port 8080)
python -m src.agent
```

## Deployment

The agent includes a CDK stack (`cdk/stack.py`) for deploying supporting infrastructure (S3 bucket, DynamoDB table). Refer to the repository-level [deployment guide](../../../docs/deployment.md) for details.