# Automotive Technical Design Generator

The Technical Design Generator transforms validated requirements documents into comprehensive technical design documents for automotive software development. 

The automotive technical design generator is implemented using Strands Agents framework and deployed on Amazon Bedrock AgentCore Runtime. The agent takes business requirements docuemtns (BRD), software requirements specification (SRS), and other supporting documents as input. During generation it follows the guidelines exposed as MCP endpoints via AgenCore Gateway.


## Architecture

```
┌─────────────────┐    ┌──────────────────────────┐             ┌─────────────────┐
│   MCP Client    │───▶│  AgentCore Runtime       │──generates─▶│  Technical      │
│ (design-server) │    │  Design Agent (Strands)  │             │  Design         │
└─────────────────┘    └──────────────────────────┘             └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐    ┌────────────────────────┐
                       │  AgentCore       │───▶│  Technical Guidelines  │
                       │  Gateway         │    │  (via Lambda)          │
                       └──────────────────┘    └────────────────────────┘
```

- **Agent**: Design generation
- **Framework**: Strands Agents with AgentCore Gateway integration
- **Authentication**: Amazon Cognito with JWT tokens
- **Runtime**: Amazon Bedrock AgentCore Runtime
- **Model**: Amazon Nova 2 Lite
- **Guidelines**: S3-stored design guidelines accessed via AgentCore Gateway

## Components

### 1. Design Generator Agent (`mcp_agent.py`)
- **Primary Agent**: Generates comprehensive technical design documents
- **Model**: Amazon Nova 2 Lite for high-quality design generation
- **Tools**: AgentCore Gateway tools for accessing design guidelines
- **Output**: Complete technical design with architecture, safety, and implementation sections

### 2. AgentCore Gateway Integration
- **S3 Guidelines**: Design guidelines stored in S3 bucket
- **Lambda Functions**: Retrieve guidelines by type and category
- **JWT Authentication**: Secure access using Cognito tokens
- **MCP Protocol**: Standard Model Context Protocol interface

### 3. Infrastructure (CloudFormation)
- **S3 Bucket**: Stores design guidelines and templates
- **Lambda Functions**: Guidelines retrieval and processing
- **IAM Roles**: Proper permissions for AgentCore and Gateway
- **Cognito Integration**: JWT-based authentication

## Getting Started

### Prerequisites
- Python 3.13+ (Recommended: virtual environment at workspace level created and top level requirements installed)
- AWS CLI configured for a US based region
- Amazon Bedrock access
- AgentCore Runtime permissions

### 1. Deploy Infrastructure Interactively (via Notebooks)
This section describes the deployment via notebooks. If you want to deploy via ma3t toolkit, refer to  [parent README](../README.md)

Run notebook cells. This will deploy the agent to the agentcore runtime and an MCP server retrieving guidelines to AgentCore Gateway.

### 2. Adjust the Settings/Steering Files for Local IDE
- For Kiro, use the files under `./ide-support/kiro` folder (choose files selectively based on your agent).
- For Cline, use `./ide-support/cline`.
- Adjust the Cognito Client-Id from your deployment from step 1.
- Adjust your local Python path to the `design-server.py` if necessary.
- Adjust your Python path if necessary.

### Troubleshooting

If you encounter deployment issues:

1. Ensure all dependencies are installed
2. Check AWS credentials are configured
3. Review the notebook output for specific error messages

For 424 "Failed Dependency" errors, the issue is typically related to:
- Missing dependencies in requirements.txt
- Docker container build failures
- Import errors in the Python code


