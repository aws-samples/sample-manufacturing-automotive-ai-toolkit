# Development Guide

This guide covers development conventions and best practices for the MA3T toolkit, including both CDK infrastructure development and AgentCore agent development.

## CDK Development Conventions

### Project Structure

```
cdk/
├── app.py                      # CDK app entry point
├── requirements.txt            # Python dependencies
├── stacks/
│   ├── main_stack.py          # Main infrastructure stack
│   ├── constructs/            # Reusable CDK constructs
│   │   ├── agentcore.py       # AgentCore deployment construct
│   │   ├── bedrock.py         # Bedrock agents construct
│   │   ├── compute.py         # Lambda and compute resources
│   │   ├── iam.py             # IAM roles and policies
│   │   ├── storage.py         # S3 buckets and storage
│   │   └── codebuild.py       # CodeBuild projects
│   └── nested_stack_registry.py # Agent discovery and registration
└── test/                      # CDK unit tests
```

### Coding Standards

#### 1. Type Hints
Always use type hints for better IDE support and code clarity:

```python
from typing import Dict, List, Optional, Any
from constructs import Construct
import aws_cdk as cdk

class MyConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id)
```

#### 2. Documentation
Document all classes and methods with docstrings:

```python
class StorageConstruct(Construct):
    """
    Creates S3 buckets and storage resources for the MA3T toolkit.
    
    This construct manages:
    - Code storage bucket
    - Temporary deployment bucket
    - Agent artifact storage
    """
    
    def create_bucket(self, bucket_name: str, versioned: bool = True) -> s3.Bucket:
        """
        Create an S3 bucket with standard security settings.
        
        Args:
            bucket_name: Name of the S3 bucket
            versioned: Whether to enable versioning (default: True)
            
        Returns:
            The created S3 bucket construct
        """
```

#### 3. Resource Naming
Use consistent naming conventions:

```python
# Use descriptive names with construct prefix
self.code_bucket = s3.Bucket(
    self, "CodeBucket",
    bucket_name=f"ma3t-code-{account_id}-{region}",
    removal_policy=cdk.RemovalPolicy.RETAIN
)

# Export important resources as properties
@property
def code_bucket_name(self) -> str:
    return self.code_bucket.bucket_name
```

#### 4. Environment Variables and Context
Use CDK context for configuration:

```python
# In app.py or stack
bedrock_model = self.node.try_get_context("bedrock_model") or "anthropic.claude-3-haiku-20240307-v1:0"

# Access in constructs
model_id = cdk.CfnParameter(
    self, "BedrockModelId",
    type="String",
    default=bedrock_model,
    description="Bedrock model ID for agents"
)
```

### Creating New Constructs

#### 1. Base Structure
```python
from constructs import Construct
import aws_cdk as cdk
from aws_cdk import aws_lambda as lambda_

class MyConstruct(Construct):
    """Description of what this construct does."""
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id)
        
        # Initialize properties
        self._lambda_function: Optional[lambda_.Function] = None
        
        # Create resources
        self._create_resources()
    
    def _create_resources(self) -> None:
        """Create the AWS resources for this construct."""
        # Implementation here
        pass
    
    @property
    def lambda_function(self) -> lambda_.Function:
        """Get the Lambda function created by this construct."""
        if not self._lambda_function:
            raise ValueError("Lambda function not created")
        return self._lambda_function
```

#### 2. Adding to Main Stack
```python
# In main_stack.py
from .constructs.my_construct import MyConstruct

class MainStack(cdk.Stack):
    def _create_shared_infrastructure(self) -> None:
        # Create construct
        self.my_construct = MyConstruct(
            self, "MyConstruct",
            # Pass any required parameters
        )
        
        # Use outputs from other constructs
        self.my_construct.configure_with_storage(self.storage.code_bucket)
```

### Testing CDK Code

#### 1. Unit Tests
Create unit tests for your constructs:

```python
# test/test_my_construct.py
import aws_cdk as cdk
from aws_cdk import assertions
from stacks.constructs.my_construct import MyConstruct

def test_my_construct_creates_lambda():
    app = cdk.App()
    stack = cdk.Stack(app, "TestStack")
    
    # Create construct
    construct = MyConstruct(stack, "TestConstruct")
    
    # Create template
    template = assertions.Template.from_stack(stack)
    
    # Assert resources are created
    template.has_resource_properties("AWS::Lambda::Function", {
        "Runtime": "python3.9",
        "Handler": "index.handler"
    })
```

#### 2. Integration Tests
Test actual deployments:

```python
# test/test_deployment.py
import boto3
import pytest
from moto import mock_s3, mock_lambda

@mock_s3
@mock_lambda
def test_deployment_creates_resources():
    # Test deployment logic
    pass
```

## AgentCore Development Conventions

### Agent Structure

```
your-agent/
├── manifest.json              # Agent metadata and configuration
├── .bedrock_agentcore.yaml   # AgentCore deployment configuration
├── agent.py                  # Main agent implementation
├── requirements.txt          # Python dependencies
├── tools/                    # Agent tools and functions
│   ├── __init__.py
│   └── my_tool.py
├── tests/                    # Agent unit tests
│   ├── __init__.py
│   └── test_agent.py
└── README.md                 # Agent documentation
```

### Manifest Configuration

#### Basic Manifest
```json
{
  "agents": [
    {
      "id": "my-agent",
      "name": "My Agent",
      "description": "Description of what this agent does",
      "type": "agentcore",
      "entrypoint": "agent.py",
      "tags": ["manufacturing", "quality-control"],
      "version": "1.0.0",
      "author": "Your Name",
      "dependencies": {
        "python": ">=3.9",
        "packages": ["requests", "pandas"]
      }
    }
  ]
}
```

#### Advanced Manifest with Tools
```json
{
  "agents": [
    {
      "id": "advanced-agent",
      "name": "Advanced Agent",
      "description": "Agent with custom tools and configuration",
      "type": "agentcore",
      "entrypoint": "agent.py",
      "tags": ["advanced", "tools"],
      "version": "1.0.0",
      "tools": [
        {
          "name": "data_processor",
          "description": "Process manufacturing data",
          "file": "tools/data_processor.py"
        }
      ],
      "environment": {
        "AGENT_LOG_LEVEL": "INFO",
        "MAX_RETRIES": "3"
      },
      "resources": {
        "memory": "512MB",
        "timeout": "300s"
      }
    }
  ]
}
```

### AgentCore Configuration

#### .bedrock_agentcore.yaml
```yaml
# AgentCore deployment configuration
apiVersion: v1
kind: AgentCore
metadata:
  name: my-agent
  namespace: ma3t
spec:
  runtime: python3.9
  handler: agent.handler
  memory: 512
  timeout: 300
  environment:
    - name: LOG_LEVEL
      value: INFO
    - name: BEDROCK_REGION
      value: us-west-2
  dependencies:
    - requirements.txt
  tools:
    - name: my_tool
      path: tools/my_tool.py
```

### Agent Implementation Patterns

#### 1. Basic Agent Structure
```python
# agent.py
import json
import logging
from typing import Dict, Any, List
from bedrock_agentcore import Agent, Tool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MyAgent(Agent):
    """
    My custom agent implementation.
    
    This agent handles manufacturing quality control tasks.
    """
    
    def __init__(self):
        super().__init__()
        self.name = "My Agent"
        self.description = "Handles quality control tasks"
        
    def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming requests.
        
        Args:
            request: The incoming request data
            
        Returns:
            Response data
        """
        try:
            # Extract request parameters
            action = request.get('action')
            data = request.get('data', {})
            
            # Route to appropriate handler
            if action == 'analyze_quality':
                return self._analyze_quality(data)
            elif action == 'generate_report':
                return self._generate_report(data)
            else:
                return {
                    'error': f'Unknown action: {action}',
                    'status': 'error'
                }
                
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            return {
                'error': str(e),
                'status': 'error'
            }
    
    def _analyze_quality(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze quality metrics."""
        # Implementation here
        return {
            'status': 'success',
            'analysis': 'Quality analysis results'
        }
    
    def _generate_report(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate quality report."""
        # Implementation here
        return {
            'status': 'success',
            'report': 'Generated report'
        }

# Handler function for AgentCore
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler function for AgentCore.
    
    Args:
        event: Lambda event data
        context: Lambda context
        
    Returns:
        Response data
    """
    agent = MyAgent()
    return agent.process_request(event)
```

#### 2. Agent with Custom Tools
```python
# tools/my_tool.py
from bedrock_agentcore import Tool
from typing import Dict, Any

class DataProcessorTool(Tool):
    """Tool for processing manufacturing data."""
    
    def __init__(self):
        super().__init__()
        self.name = "data_processor"
        self.description = "Process and analyze manufacturing data"
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool with given parameters.
        
        Args:
            parameters: Tool execution parameters
            
        Returns:
            Tool execution results
        """
        data = parameters.get('data', [])
        operation = parameters.get('operation', 'analyze')
        
        if operation == 'analyze':
            return self._analyze_data(data)
        elif operation == 'transform':
            return self._transform_data(data)
        else:
            return {'error': f'Unknown operation: {operation}'}
    
    def _analyze_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze the provided data."""
        # Implementation here
        return {
            'status': 'success',
            'analysis': 'Data analysis results'
        }
    
    def _transform_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Transform the provided data."""
        # Implementation here
        return {
            'status': 'success',
            'transformed_data': data
        }
```

### Testing Agents

#### 1. Unit Tests
```python
# tests/test_agent.py
import unittest
from unittest.mock import patch, MagicMock
from agent import MyAgent

class TestMyAgent(unittest.TestCase):
    
    def setUp(self):
        self.agent = MyAgent()
    
    def test_analyze_quality(self):
        """Test quality analysis functionality."""
        request = {
            'action': 'analyze_quality',
            'data': {'metrics': [1, 2, 3, 4, 5]}
        }
        
        response = self.agent.process_request(request)
        
        self.assertEqual(response['status'], 'success')
        self.assertIn('analysis', response)
    
    def test_unknown_action(self):
        """Test handling of unknown actions."""
        request = {
            'action': 'unknown_action',
            'data': {}
        }
        
        response = self.agent.process_request(request)
        
        self.assertEqual(response['status'], 'error')
        self.assertIn('Unknown action', response['error'])

if __name__ == '__main__':
    unittest.main()
```

#### 2. Integration Tests
```python
# tests/test_integration.py
import json
import boto3
from moto import mock_lambda
from agent import handler

@mock_lambda
def test_lambda_handler():
    """Test the Lambda handler function."""
    event = {
        'action': 'analyze_quality',
        'data': {'metrics': [1, 2, 3]}
    }
    
    context = MagicMock()
    response = handler(event, context)
    
    assert response['status'] == 'success'
```

## Creating New Nested Stacks

### 1. Agent-Specific Stacks
For complex agents that need their own infrastructure:

```python
# stacks/agents/my_agent_stack.py
import aws_cdk as cdk
from constructs import Construct
from aws_cdk import aws_lambda as lambda_

class MyAgentStack(cdk.NestedStack):
    """Nested stack for My Agent infrastructure."""
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Create agent-specific resources
        self._create_lambda_function()
        self._create_api_gateway()
        self._create_database()
    
    def _create_lambda_function(self) -> None:
        """Create the Lambda function for this agent."""
        self.lambda_function = lambda_.Function(
            self, "AgentFunction",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="agent.handler",
            code=lambda_.Code.from_asset("agents/my-agent"),
            timeout=cdk.Duration.minutes(5),
            memory_size=512
        )
```

### 2. Registering with Main Stack
```python
# In main_stack.py
from .agents.my_agent_stack import MyAgentStack

class MainStack(cdk.Stack):
    def _setup_agent_registry(self) -> None:
        """Set up agent registry and deploy agents."""
        # Create nested stack for complex agents
        self.my_agent_stack = MyAgentStack(
            self, "MyAgentStack",
            # Pass shared resources
            storage_bucket=self.storage.code_bucket
        )
```

## Best Practices

### CDK Best Practices

1. **Use Constructs**: Create reusable constructs for common patterns
2. **Environment Agnostic**: Use CDK context and parameters for environment-specific values
3. **Resource Tagging**: Tag all resources consistently
4. **Security**: Follow least-privilege principle for IAM roles
5. **Testing**: Write unit tests for all constructs
6. **Documentation**: Document all public methods and classes

### AgentCore Best Practices

1. **Error Handling**: Always handle exceptions gracefully
2. **Logging**: Use structured logging for better debugging
3. **Validation**: Validate all input parameters
4. **Testing**: Write comprehensive unit and integration tests
5. **Documentation**: Document agent capabilities and usage
6. **Performance**: Optimize for Lambda cold starts and execution time

### General Development Practices

1. **Version Control**: Use semantic versioning for agents
2. **Code Review**: All changes should be reviewed
3. **CI/CD**: Automate testing and deployment
4. **Monitoring**: Implement proper logging and monitoring
5. **Security**: Follow security best practices for cloud development