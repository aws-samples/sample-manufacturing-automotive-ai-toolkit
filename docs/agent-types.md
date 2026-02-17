# Agent Types

MA3T supports two types of agents with different deployment characteristics.

## Bedrock Agents

**Type**: `bedrock`

### Overview
Native AWS Bedrock agents managed entirely by the AWS Bedrock service.

### Use Cases
- Agents leveraging Bedrock's built-in capabilities
- Knowledge base integration
- Action groups with Lambda functions
- Managed agent lifecycle

### Deployment
- **Requires CDK**: Always needs infrastructure to create Bedrock agent resources
- Automatically deployed as part of the main CDK stack
- No containerization needed - fully managed by AWS
- Infrastructure creates: agent, knowledge bases, action groups, IAM roles

### Example Structure
```
agents_catalog/standalone_agents/01-my-bedrock-agent/
├── manifest.json
├── README.md
└── cdk/
    └── stack.py          # Creates Bedrock agent resources
```

### Manifest Configuration
```json
{
  "agents": [{
    "id": "my_bedrock_agent",
    "name": "My Bedrock Agent",
    "type": "bedrock",
    "bedrock": {
      "agentName": "AWS-Bedrock-Agent-Name"
    }
  }],
  "infrastructure": {
    "cdk": true,
    "stack_class": "MyBedrockAgentStack",
    "stack_path": "cdk/stack.py"
  }
}
```

---

## AgentCore Agents

**Type**: `agentcore`

### Overview
Container-based agents using the Bedrock AgentCore framework. Supports multiple agent frameworks.

### Supported Frameworks
- **Strands** - AWS's agent framework
- **LangGraph** - LangChain's graph-based agents
- **CrewAI** - Multi-agent orchestration
- **LlamaIndex** - Data-augmented agents

### Use Cases
- Complex custom logic
- External API integrations
- Multi-agent orchestration
- Custom data processing
- Agents requiring specific Python packages

### Deployment
- **CDK Optional**: Only needed for custom AWS resources
- Containerized and deployed to AWS (ECS/Lambda)
- Can run standalone without additional infrastructure
- Infrastructure only for: databases, APIs, storage, etc.

### Example Structures

**Without Infrastructure** (Simple agent):
```
agents_catalog/standalone_agents/02-my-agentcore-agent/
├── manifest.json
├── README.md
├── agent.py              # Agent implementation
└── requirements.txt      # Python dependencies
```

**With Infrastructure** (Needs AWS resources):
```
agents_catalog/standalone_agents/03-complex-agent/
├── manifest.json
├── README.md
├── agent.py
├── requirements.txt
└── cdk/
    └── stack.py          # Creates DynamoDB, S3, etc.
```

### Manifest Configuration

**Without Infrastructure**:
```json
{
  "agents": [{
    "id": "simple_agent",
    "name": "Simple Agent",
    "type": "agentcore",
    "entrypoint": "agent.py"
  }]
}
```

**With Infrastructure**:
```json
{
  "agents": [{
    "id": "complex_agent",
    "name": "Complex Agent",
    "type": "agentcore",
    "entrypoint": "agent.py"
  }],
  "infrastructure": {
    "cdk": true,
    "stack_class": "ComplexAgentStack",
    "stack_path": "cdk/stack.py"
  }
}
```

---

## Next Steps

- [Adding Agents](adding-agents.md) - Create your first agent
- [Infrastructure Setup](infrastructure-setup.md) - When and how to use CDK
- [Project Structure](project-structure.md) - Organize your agent code
