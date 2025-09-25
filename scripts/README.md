# MA3T Scripts Directory

This directory contains utility scripts for the Manufacturing & Automotive AI Toolkit (MA3T) to help with agent creation, deployment, and management.

## Available Scripts

### 1. `create_agent.py`
Interactive script for creating new agents in the MA3T framework.

**Purpose**: Guides users through the process of creating a new agent with proper directory structure and manifest file.

**Usage**:
```bash
python scripts/create_agent.py
```

**Features**:
- Interactive prompts for agent configuration
- Automatic ID sanitization from agent names
- Support for both standalone agents and multi-agent collaborations
- Generates proper manifest.json files
- Creates appropriate directory structure
- Supports both Bedrock and AgentCore agent types

**Prompts Include**:
- Agent name and description
- Agent type (bedrock/agentcore)
- Deployment type (standalone/collaboration)
- Entry point file specification
- Version information
- Capabilities and limitations
- Tags and categories

### 2. `build_launch_agentcore.py`
Deployment script for AgentCore-compatible agents.

**Purpose**: Scans the agents catalog and deploys AgentCore agents using the bedrock_agentcore_starter_toolkit.

**Usage**:
```bash
python scripts/build_launch_agentcore.py [options]
```

**Features**:
- Automatic discovery of AgentCore agents in the catalog
- Integration with bedrock_agentcore_starter_toolkit
- AWS account ID detection
- Configurable deployment parameters
- Logging and error handling

**Key Functions**:
- `find_agentcore_agents()`: Scans for agents with type 'agentcore'
- `get_account_id()`: Retrieves current AWS account ID
- Deployment configuration and launch

## Requirements

Install the required dependencies:

```bash
pip install -r scripts/requirements.txt
```

**Dependencies**:
- `bedrock-agentcore-starter-toolkit`: For AgentCore agent deployment
- `inquirer`: For interactive command-line prompts

## Prerequisites

Before using these scripts, ensure you have:

1. **AWS Credentials**: Properly configured AWS credentials with necessary permissions
2. **Python Environment**: Python 3.7+ with required packages installed
3. **Agent Catalog Structure**: Proper directory structure in `agents_catalog/`

## Directory Structure

The scripts expect the following directory structure:

```
agents_catalog/
├── standalone_agents/
│   └── [agent-directories]/
└── multi_agent_collaboration/
    └── [collaboration-directories]/
```

Each agent directory should contain:
- `manifest.json`: Agent configuration and metadata
- Agent implementation files
- Any additional resources

## Manifest File Format

The scripts work with manifest files in the following format:

```json
{
  "agents": [
    {
      "id": "agent-id",
      "name": "Agent Name",
      "type": "agentcore|bedrock",
      "entrypoint": "agent.py",
      "version": "1.0.0",
      "description": "Agent description",
      "tags": ["tag1", "tag2"],
      "capabilities": ["capability1", "capability2"],
      "limitations": ["limitation1", "limitation2"]
    }
  ]
}
```

## Usage Examples

### Creating a New Agent
```bash
# Run the interactive agent creation script
python scripts/create_agent.py

# Follow the prompts to configure your agent
# The script will create the directory structure and manifest file
```

### Deploying AgentCore Agents
```bash
# Deploy all AgentCore agents found in the catalog
python scripts/build_launch_agentcore.py

# The script will automatically discover and deploy agents
```

## Integration with MA3T

These scripts are designed to work seamlessly with the MA3T framework:

- **Agent Discovery**: The UI automatically discovers agents through manifest files
- **Deployment Integration**: Scripts work with the CloudFormation deployment process
- **Framework Support**: Compatible with both Bedrock and AgentCore agent types

## Troubleshooting

### Common Issues

1. **Missing Dependencies**: Ensure all requirements are installed
   ```bash
   pip install -r scripts/requirements.txt
   ```

2. **AWS Permissions**: Verify AWS credentials have necessary permissions for:
   - Bedrock service access
   - CloudFormation operations
   - Container registry access (for AgentCore)

3. **Directory Structure**: Ensure proper agents_catalog structure exists

### Logging

The scripts include comprehensive logging. Check console output for detailed information about:
- Agent discovery process
- Deployment status
- Error messages and troubleshooting hints

## Contributing

When adding new scripts to this directory:

1. Follow the existing naming conventions
2. Include comprehensive docstrings and comments
3. Add error handling and logging
4. Update this README with script documentation
5. Add any new dependencies to `requirements.txt`

## Related Documentation

- [Main MA3T README](../README.md)
- [Agent Creation Guide](../docs/agent-creation.md) (if available)
- [Deployment Guide](../docs/deployment.md) (if available)
