# Developing Agents for MA3T

This guide covers how to develop agents for the Manufacturing & Automotive AI Toolkit (MA3T) framework.

## Quick Start

### Using the Agent Creation Wizard

The fastest way to create a new agent is using the provided creation script:

```bash
cd scripts
python -m pip install -r requirements.txt
python scripts/create_agent.py
```

This interactive wizard will:
- Prompt for agent details (name, description, type)
- Set up the proper folder structure
- Generate manifest.json with correct format
- Create boilerplate code and documentation
- Optionally set up CDK infrastructure

#### Tips:

When to include infrastructure:
- **Bedrock agents**: Always required - CDK creates the Bedrock agent resources
- **AgentCore agents**: Only when you need custom resources (DynamoDB, Lambda, S3, etc.)

Deployment behavior:
The build system automatically:
1. Scans manifest.json files in the catalog
2. For agents with `infrastructure.cdk: true`:
   - Deploys the CDK stack as a nested stack
   - Passes agent metadata to the stack
   - Handles dependencies between stacks
3. For AgentCore agents without infrastructure:
   - Deploys directly to the container runtime
   - No additional AWS resources created

### Manual Setup

If you prefer manual setup, follow the [Detailed Development Guide](#detailed-development-guide) below.

## Agent Types

MA3T supports two agent types with different deployment characteristics:

### Bedrock Agents
- **Type**: `bedrock`
- **Description**: Native AWS Bedrock agents managed by the service
- **Use Case**: Agents that leverage Bedrock's built-in capabilities (knowledge bases, action groups, etc.)
- **Deployment**: 
  - **Requires CDK**: Always needs CDK infrastructure to create the Bedrock agent resources
  - Automatically deployed as part of the main CDK stack
  - No containerization needed - managed by AWS Bedrock service
- **Infrastructure**: CDK stack creates Bedrock agent, knowledge bases, action groups, and IAM roles

### AgentCore Agents  
- **Type**: `agentcore`
- **Description**: Container-based agents using the Bedrock AgentCore framework
- **Frameworks**: Supports Strands, LangGraph, CrewAI, and LlamaIndex
- **Use Case**: Complex agents requiring custom logic, external APIs, or multi-agent orchestration
- **Deployment**: 
  - **CDK Optional**: Only needs CDK if you require custom AWS resources
  - Containerized and deployed to AWS infrastructure (ECS/Lambda)
  - Can run standalone without additional infrastructure
- **Infrastructure**: Optional CDK stack for custom resources (databases, APIs, etc.)

## Deployment Categories

### Development Deployment

For faster development cycles, you can skip CDK security checks:

```bash
./deploy_cdk.sh --skip-nag
```

This bypasses cdk-nag validation rules, which is useful during development but should not be used for production deployments.

### Standalone Agents
- **Location**: `agents_catalog/standalone_agents/`
- **Purpose**: Individual agents for specific tasks
- **Naming**: `XX-agent-name/` (where XX is a sequential number)

### Multi-Agent Collaborations
- **Location**: `agents_catalog/multi_agent_collaboration/`
- **Purpose**: Groups of agents that work together
- **Naming**: `XX-collaboration-name/` (where XX is a sequential number)

## Detailed Development Guide

### 1. Project Structure

Each agent follows this structure:

```
XX-agent-name/
├── manifest.json          # Agent metadata and configuration
├── README.md             # Agent documentation
├── requirements.txt      # Python dependencies
├── src/                  # Source code
│   └── agent.py         # Main entry point
├── tests/               # Test files
│   └── test_agent.py    # Unit tests
└── cdk/                 # CDK infrastructure (optional)
    ├── stack.py         # CDK stack definition
    └── requirements.txt # CDK dependencies
```

### 2. Manifest Configuration

The `manifest.json` file defines your agent's metadata and deployment requirements:

#### Basic Structure
```json
{
  "agents": [
    {
      "id": "your_agent_id",
      "name": "Your Agent Name",
      "description": "Agent description",
      "type": "bedrock|agentcore",
      "entrypoint": "agent.py",
      "tags": ["tag1", "tag2"]
    }
  ]
}
```

#### Infrastructure Configuration
Add the `infrastructure` section when you need custom AWS resources:

```json
{
  "agents": [...],
  "infrastructure": {
    "cdk": true,
    "stack_class": "YourStack",
    "stack_path": "cdk/stack.py"
  }
}
```

#### Required Fields
- `id`: Unique identifier (alphanumeric + underscore, starts with letter, max 48 chars)
- `name`: Human-readable agent name
- `description`: Brief description of agent functionality
- `type`: Either "bedrock" or "agentcore"
- `entrypoint`: Main Python file (for agentcore agents)

#### Optional Fields
- `tags`: Array of descriptive tags
- `metadata`: Additional information about the agent
- `infrastructure`: CDK configuration (if using custom AWS resources)

### 3. Bedrock Agent Configuration

For Bedrock agents, add bedrock-specific configuration:

```json
{
  "id": "your-bedrock-agent",
  "type": "bedrock",
  "bedrock": {
    "agentName": "AWS-Bedrock-Agent-Name",
    "override": {
      "name": "Display Name",
      "role": "individual|supervisor",
      "icon": "/images/icon.png",
      "description": "UI description",
      "tags": ["tag1", "tag2"]
    }
  }
}
```

### 4. AgentCore Implementation

For AgentCore agents, implement your logic in the entrypoint file:

```python
#!/usr/bin/env python3
"""
Your Agent Name
Agent description
"""

class YourAgent:
    def __init__(self):
        # Initialize your agent
        pass
    
    def process(self, input_data):
        # Implement your agent logic
        return {"response": "Agent output"}

def main():
    agent = YourAgent()
    # Agent execution logic
    pass

if __name__ == "__main__":
    main()
```

### 5. CDK Infrastructure

#### For Bedrock Agents (Required)
Bedrock agents always need CDK to create the agent resources:

```python
from aws_cdk import Stack
from aws_cdk import aws_bedrock as bedrock
from constructs import Construct

class BedrockAgentStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        # Create Bedrock agent
        self.agent = bedrock.CfnAgent(
            self, "Agent",
            agent_name="your-agent-name",
            description="Agent description",
            foundation_model="anthropic.claude-3-sonnet-20240229-v1:0",
            instruction="Your agent instructions..."
        )
        
        # Add knowledge bases, action groups, etc.
```

#### For AgentCore Agents (Optional)
Only add CDK when you need custom AWS resources:

```python
from aws_cdk import Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

class AgentCoreStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        # Custom resources your agent needs
        self.table = dynamodb.Table(
            self, "AgentData",
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING
            )
        )
        
        # Lambda for external API calls
        self.api_function = lambda_.Function(
            self, "ApiFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="api.handler",
            code=lambda_.Code.from_asset("lambda")
        )
```

#### Nested Stack Deployment
The build system automatically:
1. Detects agents with `infrastructure.cdk: true`
2. Creates a nested stack for each agent's infrastructure
3. Deploys stacks in dependency order
4. Passes outputs between stacks as needed

**Example deployment flow:**
```
Main Stack
├── Agent1Stack (Bedrock agent + knowledge base)
├── Agent2Stack (AgentCore + DynamoDB)
└── Agent3Stack (AgentCore only - no nested stack)
```

### 6. Testing

Create comprehensive tests in the `tests/` directory:

```python
#!/usr/bin/env python3
"""
Tests for Your Agent
"""
import pytest
from src.agent import YourAgent

def test_agent_initialization():
    agent = YourAgent()
    assert agent is not None

def test_agent_processing():
    agent = YourAgent()
    result = agent.process({"test": "input"})
    assert "response" in result
```

### 7. Documentation

Create a detailed README.md:

```markdown
# Your Agent Name

Brief description of what your agent does.

## Features

- Feature 1
- Feature 2

## Setup

1. Install dependencies:
   pip install -r requirements.txt

2. Configure environment variables (if needed)

## Usage

Describe how to use your agent.

## Testing

python -m pytest tests/
```

## Best Practices

### Security
- Never hardcode credentials or secrets
- Use environment variables for configuration
- Validate all inputs
- Follow AWS security best practices

### Documentation
- Keep README.md up to date
- Document all configuration options
- Include usage examples
- Explain any complex logic

## Framework Integration

### Agent Discovery
The framework automatically discovers agents by scanning the catalog directories and reading manifest.json files.

### UI Integration
Agents are automatically registered in the Next.js UI based on their manifest configuration. The UI provides:
- Single pane of glass for all agents
- Automatic agent discovery
- Interactive chat interface

### Deployment
The CDK deployment framework handles:
- Infrastructure provisioning via nested stacks
- Automatic detection of agents requiring CDK
- Agent deployment via CodeBuild
- Resource management and dependencies
- Environment configuration

**Deployment Types:**
- **Bedrock agents**: Always deployed with CDK nested stack
- **AgentCore with infrastructure**: Deployed with CDK nested stack  
- **AgentCore without infrastructure**: Direct container deployment

## Troubleshooting

### Common Issues

**Agent ID validation errors**
- Ensure ID starts with a letter
- Use only alphanumeric characters and underscores
- Keep under 48 characters

**Manifest validation errors**
- Verify JSON syntax is correct
- Check all required fields are present
- Ensure agent type is "bedrock" or "agentcore"

**CDK deployment failures**
- Verify AWS credentials are configured
- Check CDK stack syntax
- Ensure required permissions are available

### Getting Help

1. Check the existing agent examples in the catalog
2. Review the framework documentation
3. Open an issue in the repository for bugs or feature requests

## Contributing

When contributing agents to the framework:

1. Follow the established naming conventions
2. Include comprehensive tests
3. Document your agent thoroughly
4. Ensure your agent follows security best practices
5. Test your agent in the full framework environment

See [CONTRIBUTING.md](../CONTRIBUTING.md) for detailed contribution guidelines.
