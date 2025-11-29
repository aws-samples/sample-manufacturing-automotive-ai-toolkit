# Manifest Configuration

The `manifest.json` file defines your agent's metadata and deployment configuration.

## Basic Structure

```json
{
  "group": ["Category Name"],
  "agents": [{
    "id": "agent_id",
    "name": "Agent Name",
    "version": "1.0.0",
    "description": "What this agent does",
    "type": "bedrock|agentcore",
    "entrypoint": "agent.py"
  }]
}
```

## Required Fields

### `id` (string)
Unique identifier for your agent.

**Rules:**
- Must start with a letter
- Only alphanumeric characters and underscores
- Maximum 48 characters
- Example: `my_agent_123`

### `name` (string)
Human-readable agent name displayed in the UI.

Example: `"My Agent Name"`

### `type` (string)
Agent type: `"bedrock"` or `"agentcore"`

See [Agent Types](agent-types.md) for details.

### `description` (string)
Brief description of what the agent does.

## Optional Fields

### `version` (string)
Semantic version of your agent.

Example: `"1.0.0"`

### `entrypoint` (string)
Main Python file for AgentCore agents.

Example: `"agent.py"`

### `group` (array)
Categories for organizing agents in the UI.

Example: `["Manufacturing", "Quality Control"]`

### `tags` (array)
Descriptive tags for your agent.

Example: `["diagnostics", "automotive"]`

### `metadata` (object)
Additional custom metadata.

```json
{
  "metadata": {
    "authors": [{"name": "Your Name", "organization": "Company"}],
    "created_date": "2025-01-01",
    "maturity": "development"
  }
}
```

## Infrastructure Configuration

Add when your agent needs AWS resources:

```json
{
  "agents": [...],
  "infrastructure": {
    "cdk": true,
    "stack_class": "MyAgentStack",
    "stack_path": "cdk/stack.py"
  }
}
```

### `cdk` (boolean)
Set to `true` to enable CDK infrastructure.

### `stack_class` (string)
Name of your CDK stack class.

Must match the class name in your `stack.py` file.

### `stack_path` (string)
Relative path to your CDK stack file.

Example: `"cdk/stack.py"`

## SSM Parameter Mapping (AgentCore Only)

For AgentCore agents, automatically store runtime ARNs in SSM Parameter Store after deployment:

```json
{
  "agents": [{
    "id": "my_agentcore_agent",
    "type": "agentcore"
  }],
  "ssm_parameter_mapping": {
    "my_agentcore_agent": "/my-app/agentcore-runtime/main"
  }
}
```

### How It Works

1. Agent deploys to AgentCore and receives a runtime ARN
2. Build script automatically updates the SSM parameter with the runtime ARN
3. Your application can retrieve the ARN from SSM to invoke the agent

### Use Cases

- **Multi-agent systems**: Store each agent's runtime ARN for agent-to-agent communication
- **UI integration**: Retrieve runtime ARNs to display agent status
- **Lambda functions**: Read runtime ARNs to invoke agents programmatically

### Example: Multi-Agent System

```json
{
  "agents": [{
    "id": "orchestrator_agent",
    "type": "agentcore",
    "entrypoint": "orchestrator.py"
  }],
  "ssm_parameter_mapping": {
    "orchestrator_agent": "/quality-inspection/agentcore-runtime/orchestrator"
  }
}
```

After deployment, retrieve the runtime ARN:

```python
import boto3

ssm = boto3.client('ssm')
response = ssm.get_parameter(Name='/quality-inspection/agentcore-runtime/orchestrator')
runtime_arn = response['Parameter']['Value']
```

## Bedrock Agent Configuration

For Bedrock agents, add bedrock-specific settings:

```json
{
  "agents": [{
    "id": "my_bedrock_agent",
    "type": "bedrock",
    "bedrock": {
      "agentName": "AWS-Bedrock-Agent-Name",
      "override": {
        "name": "Display Name",
        "role": "individual",
        "icon": "/images/icon.png",
        "description": "UI description"
      }
    }
  }]
}
```

## Complete Example

```json
{
  "group": ["Manufacturing", "Quality Control"],
  "agents": [{
    "id": "quality_inspector",
    "name": "Quality Inspector Agent",
    "version": "1.0.0",
    "description": "Analyzes product quality metrics and identifies defects",
    "type": "agentcore",
    "entrypoint": "agent.py",
    "tags": ["quality", "inspection", "manufacturing"],
    "metadata": {
      "authors": [{
        "name": "Engineering Team",
        "organization": "ACME Corp"
      }],
      "created_date": "2025-01-15",
      "maturity": "production"
    }
  }],
  "infrastructure": {
    "cdk": true,
    "stack_class": "QualityInspectorStack",
    "stack_path": "cdk/stack.py"
  },
  "ssm_parameter_mapping": {
    "quality_inspector": "/quality-inspector/agentcore-runtime/main"
  }
}
```

## Validation

The framework validates your manifest during deployment. Common errors:

- **Invalid ID**: Must start with letter, alphanumeric + underscore only
- **Missing required fields**: `id`, `name`, `type` are required
- **Invalid type**: Must be `"bedrock"` or `"agentcore"`
- **Missing stack file**: If `infrastructure.cdk: true`, stack file must exist

## Next Steps

- [Adding Agents](adding-agents.md) - Create your first agent
- [Agent Types](agent-types.md) - Choose the right agent type
- [Infrastructure Setup](infrastructure-setup.md) - Add AWS resources
