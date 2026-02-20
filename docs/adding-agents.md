# Adding Agents to MA3T

This guide shows you how to add a new agent to the Manufacturing & Automotive AI Toolkit.

## Quick Start: Using the Wizard

The fastest way to create an agent:

### Step 1: Install Script Dependencies

```bash
cd scripts
pip install -r requirements.txt
```

This installs:
- `inquirer` - Interactive prompts
- `bedrock-agentcore-starter-toolkit` - AgentCore utilities

### Step 2: Run the Wizard

```bash
python create_agent.py
```

The wizard will prompt you for:

1. **Agent name** - Human-readable name (e.g., "Quality Inspector")
   - Automatically converted to valid ID format (e.g., `quality_inspector`)
   
2. **Description** - What your agent does

3. **Agent type** - Choose:
   - `bedrock` - Fully managed AWS Bedrock agent
   - `agentcore` - Container-based agent (Strands, LangGraph, etc.)

4. **Deployment type** - Choose:
   - `standalone` - Individual agent
   - `collaboration` - Part of multi-agent system

5. **Entry point** - Main file (default: `agent.py`)

6. **Version** - Semantic version (default: `1.0.0`)

7. **Infrastructure** - If you need AWS resources:
   - Answer "yes" if you need DynamoDB, S3, Lambda, etc.
   - Provide CDK stack class name
   - Optionally generate example CDK stack

### Step 3: What Gets Created

The wizard creates:

```
agents_catalog/{standalone_agents|multi_agent_collaboration}/XX-agent-name/
├── manifest.json          # Generated from your answers
├── README.md             # Template documentation
├── agent.py              # Boilerplate agent code (if AgentCore)
├── requirements.txt      # Python dependencies
└── cdk/                  # If you chose infrastructure
    ├── stack.py         # Example CDK stack
    └── requirements.txt # CDK dependencies
```

### Step 4: Implement Your Agent

Edit the generated `agent.py`:

```python
# The wizard creates this boilerplate
from strands import Agent

agent = Agent(name="your-agent")

# Add your tools and logic here
@agent.tool()
def my_tool():
    pass
```

### Step 5: Deploy

```bash
cd ../..  # Back to repo root
./deploy_cdk.sh
```

Your agent is now live.

## Manual Setup

If you prefer to create agents manually, follow these steps.

### Step 1: Choose Agent Type

First, decide which type of agent you need:

- **Bedrock Agent**: Fully managed by AWS, uses Bedrock's native features
- **AgentCore Agent**: Container-based, full control, supports multiple frameworks

See [Agent Types](agent-types.md) for detailed comparison.

### Step 2: Create Folder Structure

Create your agent folder in the appropriate location:

**Standalone agents:**
```
agents_catalog/standalone_agents/XX-agent-name/
```

**Multi-agent collaborations:**
```
agents_catalog/multi_agent_collaboration/XX-collaboration-name/
```

Where `XX` is a sequential number (e.g., `01`, `02`, etc.).

### Step 3: Create manifest.json

The manifest defines your agent's metadata and configuration.

**For AgentCore agents (no infrastructure):**
```json
{
  "group": ["Category Name"],
  "agents": [{
    "id": "mynewagent",
    "name": "My New Agent",
    "version": "1.0.0",
    "description": "What this agent does",
    "type": "agentcore",
    "entrypoint": "agent.py"
  }]
}
```

**For agents with infrastructure:**
```json
{
  "group": ["Category Name"],
  "agents": [{
    "id": "mynewagent",
    "name": "My New Agent",
    "version": "1.0.0",
    "description": "What this agent does",
    "type": "agentcore",
    "entrypoint": "agent.py"
  }],
  "infrastructure": {
    "cdk": true,
    "stack_class": "MyAgentStack",
    "stack_path": "cdk/stack.py"
  }
}
```

See [Manifest Configuration](manifest-configuration.md) for all options.

### Step 4: Implement Your Agent

Create your agent code in the entrypoint file:

```python
# agent.py
from strands import Agent

agent = Agent(
    name="my-new-agent",
    instructions="You are a helpful assistant that..."
)

@agent.tool()
def my_tool(param: str) -> str:
    """Tool description for the LLM"""
    # Your tool logic here
    return f"Result: {param}"

if __name__ == "__main__":
    # Test your agent locally
    response = agent.run("Hello!")
    print(response)
```

### Step 5: Add Infrastructure (Optional)

If your agent needs AWS resources (DynamoDB, S3, etc.), create a CDK stack:

```python
# cdk/stack.py
from aws_cdk import (
    NestedStack,
    aws_dynamodb as dynamodb,
    RemovalPolicy
)
from constructs import Construct

class MyAgentStack(NestedStack):
    def __init__(self, scope: Construct, construct_id: str, 
                 shared_resources=None, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        # Create your resources
        self.my_table = dynamodb.Table(
            self, "MyTable",
            table_name="MyAgent_Data",
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # Permissions are auto-granted by the framework!
        # No need to manually grant access to shared_resources['agent_role']
```

**That's it!** The framework automatically:
- Discovers your DynamoDB tables and S3 buckets
- Grants the shared agent role access to them
- No manual permission management needed

See [Infrastructure Setup](infrastructure-setup.md) for more details.

### Step 6: Add System Dependencies (Optional)

If your agent needs Linux system packages (e.g., `git`, `java`, native libraries), create a `Dockerfile.deps` file in your agent's root directory. This file contains raw Dockerfile `RUN` instructions that are injected into the generated Dockerfile at build time — so packages are baked into the container image instead of installed at runtime.

**Example** (`Dockerfile.deps`):
```dockerfile
RUN apt-get update && \
    apt-get install -y --no-install-recommends git wget gpg && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
```

The build script (`scripts/build_launch_agentcore.py`) automatically detects this file and injects its contents into the Dockerfile generated by `configure_bedrock_agentcore()`. No manifest changes are required.

> **Important:** Do not install system dependencies at agent runtime (e.g., via `subprocess.run('apt install ...')`). This slows down every cold start. Use `Dockerfile.deps` instead.

### Step 7: Add Python Dependencies

Create `requirements.txt` with your Python dependencies:

```txt
strands-agents>=1.0.0
boto3>=1.28.0
# Add your dependencies here
```

### Step 8: Deploy

Deploy your agent to AWS:

```bash
./deploy_cdk.sh
```

The framework will:
1. Discover your agent from `manifest.json`
2. Create infrastructure (if specified)
3. Auto-grant permissions to your resources
4. Deploy your AgentCore container
5. Register your agent in the UI

---

## What Happens Automatically

The MA3T framework handles these tasks for you:

**Agent Discovery** - Scans `manifest.json` files in the catalog  
**Infrastructure Creation** - Deploys your CDK stack as a nested stack  
**Permission Management** - Auto-grants access to DynamoDB tables and S3 buckets  
**Container Deployment** - Builds and deploys your AgentCore container  
**UI Registration** - Your agent appears in the web interface  

---

## Supported Auto-Granted Resources

The framework automatically grants the shared agent role access to:

- **DynamoDB Tables**: Full read/write access
- **S3 Buckets**: Full read/write access

Additional resource types can be added to `cdk/stacks/nested_stack_registry.py`.

---

## Complete Example

Here's a complete agent with infrastructure:

```
agents_catalog/standalone_agents/05-example-agent/
├── manifest.json
├── README.md
├── agent.py
├── requirements.txt
└── cdk/
    └── stack.py
```

**manifest.json:**
```json
{
  "group": ["Example Agents"],
  "agents": [{
    "id": "example_agent",
    "name": "Example Agent",
    "version": "1.0.0",
    "description": "An example agent with DynamoDB",
    "type": "agentcore",
    "entrypoint": "agent.py"
  }],
  "infrastructure": {
    "cdk": true,
    "stack_class": "ExampleAgentStack",
    "stack_path": "cdk/stack.py"
  }
}
```

**agent.py:**
```python
from strands import Agent
import boto3

agent = Agent(name="example-agent")
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('ExampleAgent_Data')

@agent.tool()
def store_data(key: str, value: str) -> str:
    """Store data in DynamoDB"""
    table.put_item(Item={'id': key, 'value': value})
    return f"Stored {key}={value}"

@agent.tool()
def get_data(key: str) -> str:
    """Retrieve data from DynamoDB"""
    response = table.get_item(Key={'id': key})
    return response.get('Item', {}).get('value', 'Not found')
```

**cdk/stack.py:**
```python
from aws_cdk import NestedStack, aws_dynamodb as dynamodb, RemovalPolicy
from constructs import Construct

class ExampleAgentStack(NestedStack):
    def __init__(self, scope, construct_id, shared_resources=None, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        self.table = dynamodb.Table(
            self, "DataTable",
            table_name="ExampleAgent_Data",
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )
```

**requirements.txt:**
```txt
strands-agents>=1.0.0
boto3>=1.28.0
```

Deploy with `./deploy_cdk.sh` and your agent is ready!

---

## Advanced: Custom Permissions

If you need permissions beyond auto-granted DynamoDB/S3 access:

```python
class MyAgentStack(NestedStack):
    def __init__(self, scope, construct_id, shared_resources=None, **kwargs):
        super().__init__(scope, construct_id, shared_resources, **kwargs)
        
        # Create resources (auto-granted)
        self.my_table = dynamodb.Table(...)
        
        # Add custom permissions
        if shared_resources and 'agent_role' in shared_resources:
            shared_resources['agent_role'].add_to_policy(
                iam.PolicyStatement(
                    actions=["secretsmanager:GetSecretValue"],
                    resources=[f"arn:aws:secretsmanager:*:*:secret:my-secret"]
                )
            )
```

---

## Testing Locally

Test your agent before deploying:

```bash
cd agents_catalog/standalone_agents/XX-agent-name
python agent.py
```

---

## Next Steps

- [Agent Types](agent-types.md) - Understand Bedrock vs AgentCore
- [Infrastructure Setup](infrastructure-setup.md) - Deep dive into CDK
- [Manifest Configuration](manifest-configuration.md) - All manifest options
- [Testing Agents](testing-agents.md) - Write tests for your agent
