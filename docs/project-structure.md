# Project Structure

This guide explains how to organize your agent code in MA3T.

## Standard Agent Structure

```
XX-agent-name/
├── manifest.json         # Agent metadata (required)
├── README.md             # Agent documentation
├── agent.py              # Main entry point (for AgentCore)
├── requirements.txt      # Python dependencies
├── tests/                # Test files (optional)
│   └── test_agent.py
└── cdk/                 # Infrastructure (optional)
    ├── stack.py         # CDK stack definition
    └── requirements.txt # CDK dependencies
```

## File Descriptions

### manifest.json (Required)
Defines agent metadata, type, and infrastructure requirements.

See [Manifest Configuration](manifest-configuration.md) for details.

### agent.py (Required for AgentCore)
Main entry point for your agent implementation.

```python
from strands import Agent

agent = Agent(name="my-agent")

@agent.tool()
def my_tool():
    pass
```

### README.md (Recommended)
Documentation for your agent including:
- What the agent does
- How to use it
- Configuration options
- Examples

### requirements.txt (Optional)
Python dependencies for your agent:

```txt
strands-agents>=1.0.0
boto3>=1.28.0
```

### tests/ (Optional)
Unit tests for your agent:

```python
import pytest
from agent import agent

def test_agent():
    response = agent.run("test")
    assert response is not None
```

### cdk/ (Optional)
Infrastructure code when you need AWS resources.

See [Infrastructure Setup](infrastructure-setup.md) for details.

## Folder Naming

### Standalone Agents
```
agents_catalog/standalone_agents/XX-agent-name/
```

Where `XX` is a sequential number: `01`, `02`, `03`, etc.

### Multi-Agent Collaborations
```
agents_catalog/multi_agent_collaboration/XX-collaboration-name/
```

## Next Steps

- [Adding Agents](adding-agents.md) - Create your first agent
- [Manifest Configuration](manifest-configuration.md) - Configure your agent
- [Infrastructure Setup](infrastructure-setup.md) - Add AWS resources
