# SFC Config Generation Agent

Accelerate Industrial Equipment Onboarding by creating, validating, and running **Shop Floor Connectivity (SFC)** configurations using AI.

## Overview

This agent leverages Amazon Bedrock (Claude) and the Strands Agents SDK to assist with SFC configuration tasks. It exposes an MCP server (`sfc-spec-mcp-server.py`) as its primary knowledge source for validation and combines it with internal tools for file operations, conversation logging, and configuration analysis.

Short-term conversational memory is provided by **Amazon Bedrock AgentCore Memory**, allowing the agent to recall context within a session (e.g. previously discussed protocol choices, module constraints, or user preferences).

## Key Capabilities

- **Create** new SFC configuration JSON files from natural-language descriptions
- **Validate** existing configurations against the SFC specification (via MCP tools)
- **Read / Save** configurations and results to cloud storage (S3 + DynamoDB)
- **Analyze** SFC modules and visualize data
- **Remember** context within a session via AgentCore short-term memory

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
- Model access enabled for the configured model (default: `us.anthropic.claude-sonnet-4-5-20250929-v1:0`)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure via environment variables
export BEDROCK_MODEL_ID="us.anthropic.claude-sonnet-4-5-20250929-v1:0"
export BEDROCK_REGION="us-east-1"
export AGENTCORE_MEMORY_ID="<memory-id>"   # output of CDK deployment

# Run the agent (exposes AgentCore API on port 8080)
python -m src.agent
```

## AgentCore Memory (short-term)

The CDK stack provisions a **basic AgentCore Memory** (no extraction strategies) via a Lambda-backed CloudFormation Custom Resource on first deploy. The memory ID is written to SSM parameter `/sfc-config-agent/memory-id` and must be injected into the container as the `AGENTCORE_MEMORY_ID` environment variable.

Each HTTP request creates a fresh `AgentCoreMemorySessionManager` scoped to the `session_id` and `actor_id` from the request payload:

| Payload key  | Required | Description |
|---|---|---|
| `prompt`     | yes | The user message |
| `session_id` | no  | Stable identifier to continue a session across turns (auto-generated if omitted) |
| `actor_id`   | no  | Stable user / actor identifier (defaults to `sfc-agent-user`) |

Pass the same `session_id` on follow-up requests within a conversation to retain in-session context.

## Deployment

The agent includes a CDK stack (`cdk/stack.py`) for deploying supporting infrastructure:

| Resource | Purpose |
|---|---|
| S3 Bucket | Stores agent-generated configs, results, and conversation logs |
| DynamoDB Table | File metadata index and content cache |
| AgentCore Memory | Short-term conversational memory (CloudFormation Custom Resource) |
| SSM Parameters | Runtime resource discovery (`/sfc-config-agent/*`) |

Refer to the repository-level [deployment guide](../../../docs/deployment.md) for full deployment instructions.