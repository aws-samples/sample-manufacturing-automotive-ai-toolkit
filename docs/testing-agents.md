# Testing Agents

This guide covers how to test your agents locally and in AWS.

## Local Testing

### Test Agent Directly

```bash
cd agents_catalog/standalone_agents/XX-agent-name
python agent.py
```

### Interactive Testing

```python
# agent.py
from strands import Agent

agent = Agent(name="my-agent")

@agent.tool()
def my_tool(param: str) -> str:
    return f"Result: {param}"

if __name__ == "__main__":
    # Test your agent
    response = agent.run("Test message")
    print(response)
```

## Unit Tests

### Create Test File

```
tests/
└── test_agent.py
```

### Write Tests

```python
import pytest
from agent import agent

def test_agent_initialization():
    """Test agent can be initialized"""
    assert agent is not None
    assert agent.name == "my-agent"

def test_tool_execution():
    """Test agent tools work"""
    response = agent.run("Use my_tool with param='test'")
    assert "Result: test" in response

@pytest.mark.asyncio
async def test_async_tool():
    """Test async tools"""
    response = await agent.run_async("Test async")
    assert response is not None
```

### Run Tests

```bash
# Install pytest
pip install pytest pytest-asyncio

# Run tests
pytest tests/

# Run with coverage
pytest --cov=agent tests/
```

## Testing with AWS Resources

### Mock AWS Services

```python
import boto3
from moto import mock_dynamodb
import pytest

@mock_dynamodb
def test_with_dynamodb():
    """Test agent with mocked DynamoDB"""
    # Create mock table
    dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
    table = dynamodb.create_table(
        TableName='MyAgent_Data',
        KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST'
    )
    
    # Test your agent
    from agent import store_data
    result = store_data('key1', 'value1')
    assert 'Stored' in result
```

### Install Mocking Libraries

```bash
pip install moto[dynamodb,s3] boto3
```

## Integration Testing

### Test Against Real AWS Resources

```python
import boto3
import os

def test_integration():
    """Test with real AWS resources"""
    # Use test environment
    table_name = os.environ.get('TEST_TABLE_NAME', 'Test_MyAgent_Data')
    
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    
    # Test operations
    table.put_item(Item={'id': 'test', 'value': 'data'})
    response = table.get_item(Key={'id': 'test'})
    
    assert response['Item']['value'] == 'data'
    
    # Cleanup
    table.delete_item(Key={'id': 'test'})
```

### Setup Test Resources

Create a separate test stack:

```python
# tests/test_stack.py
from aws_cdk import Stack, aws_dynamodb as dynamodb

class TestStack(Stack):
    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        self.test_table = dynamodb.Table(
            self, "TestTable",
            table_name="Test_MyAgent_Data",
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST
        )
```

## Testing in the UI

### Deploy and Test

```bash
# Deploy your agent
./deploy_cdk.sh

# Access UI
# Navigate to the CloudFormation output URL
# Test your agent through the chat interface
```

### Manual Testing Checklist

- [ ] Agent appears in UI
- [ ] Agent responds to messages
- [ ] Tools execute correctly
- [ ] Error handling works
- [ ] AWS resources are accessible
- [ ] Permissions are correct

## Continuous Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Test Agents

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov moto
      
      - name: Run tests
        run: pytest tests/ --cov=agent
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Best Practices

### Test Coverage
Aim for >80% code coverage:

```bash
pytest --cov=agent --cov-report=html tests/
```

### Test Organization

```
tests/
├── test_agent.py          # Agent logic tests
├── test_tools.py          # Tool-specific tests
├── test_integration.py    # AWS integration tests
└── conftest.py           # Shared fixtures
```

### Fixtures

```python
# tests/conftest.py
import pytest
from agent import agent

@pytest.fixture
def test_agent():
    """Provide agent instance for tests"""
    return agent

@pytest.fixture
def mock_table():
    """Provide mocked DynamoDB table"""
    from moto import mock_dynamodb
    with mock_dynamodb():
        # Setup mock table
        yield table
```

### Environment Variables

```python
# tests/test_agent.py
import os

def test_with_env():
    """Test with environment variables"""
    os.environ['TABLE_NAME'] = 'Test_Table'
    # Run tests
```

## Debugging

### Enable Debug Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@agent.tool()
def my_tool(param: str):
    logger.debug(f"Tool called with: {param}")
    return f"Result: {param}"
```

### Print Agent State

```python
if __name__ == "__main__":
    print(f"Agent: {agent.name}")
    print(f"Tools: {agent.tools}")
    print(f"Instructions: {agent.instructions}")
```

## Next Steps

- [Adding Agents](adding-agents.md) - Create your first agent
- [Infrastructure Setup](infrastructure-setup.md) - Add AWS resources
- [Troubleshooting](troubleshooting.md) - Debug common issues
