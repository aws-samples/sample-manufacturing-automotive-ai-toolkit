# Automotive V-Cycle Development Agents

Multi-agent V-cycle system for automotive software development, implementing requirements analysis, technical design generation, and C code compliance checking using Amazon Bedrock AgentCore.

## Architecture

The system implements three stages of the automotive V-cycle:

```
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│  Requirements       │───▶│  Design              │───▶│  C Code             │
│  Analyzer           │    │  Generator           │    │  Analyzer           │
└─────────────────────┘    └──────────────────────┘    └─────────────────────┘
  Analyzes BRDs for          Generates technical        Checks automotive
  consistency, generates     designs from validated     coding standards,
  acceptance tests           requirements via           generates unit tests
                             Gateway MCP tools          conditionally
```

Each agent is a Strands multi-agent graph deployed to Amazon Bedrock AgentCore Runtime with JWT authentication via Amazon Cognito.

## Agents

### Requirements Analyzer (`requirements-agent/`)
- Analyzes business requirements documents for consistency and completeness
- Conditionally generates user acceptance tests using a graph pattern
- Model: Amazon Nova Lite 2

### Design Generator (`design-agent/`)
- Generates comprehensive technical design documents from validated BRD and SRS
- Integrates with AgentCore Gateway to retrieve design guidelines from S3
- Model: Amazon Nova Lite 2

### C Code Analyzer (`c-code-analyzer-agent/`)
- Analyzes C code against custom automotive coding standards (MISRA-C based)
- Conditionally generates unit tests if no severe violations found
- Model: Amazon Nova Lite 2

## Project Structure

```
01-automotive-vcycle/
├── manifest.json                 # Top-level CDK + notebook metadata
├── cdk/stack.py                  # NestedStack: S3, Lambda, IAM for guidelines
├── guidelines/                   # Design guideline documents (deployed to S3)
├── sample-data/                  # Sample BRD, SRS, and C code files
├── requirements-agent/           # Agent source + Dockerfile + manifest
├── design-agent/                 # Agent source + Dockerfile + manifest
├── c-code-analyzer-agent/        # Agent source + Dockerfile + manifest
├── notebooks/                    # Interactive development notebooks
│   ├── utils.py                  # Shared Cognito/IAM/Gateway utilities
│   ├── 01-requirements-analyzer.ipynb
│   ├── 02-design-generator.ipynb
│   └── 03-c-code-analyzer.ipynb
└── mcp-servers/                  # MCP server implementations
```

## Deployment

### Automated (via MA3T CDK)

The project integrates with MA3T's deployment pipeline:

1. **CDK stack** is discovered by `nested_stack_registry.py` via the top-level `manifest.json`
2. **Per-agent manifests** are discovered by `build_launch_agentcore.py` via `os.walk`
3. Run `cd ma3t && ./deploy_cdk.sh` to deploy infrastructure and agents

### Interactive (via Notebooks)

For development and experimentation:

1. Open the notebooks in a SageMaker notebook instance or locally
2. Follow each notebook sequentially: requirements → design → C code analysis
3. Each notebook handles its own Cognito setup, agent deployment, and testing

## Prerequisites

- Python 3.13+
- AWS credentials configured for a US-based region
- Amazon Bedrock model access (Amazon Nova Lite 2)
- Required Python packages (see each agent's `requirements.txt`)

## CDK Infrastructure

The `cdk/stack.py` creates:
- **S3 bucket** with versioned design guideline documents
- **Lambda function** for retrieving guidelines (used by AgentCore Gateway)
- **IAM role** for AgentCore Gateway to invoke Lambda and read S3

## Sample Data

- `sample-data/weather-app/` - Weather application BRD and SRS documents
- `sample-data/sample-c-code/` - C code samples with varying compliance levels
