# Testing Agents

How to test your agents before deploying to AWS.

## Local Testing

### Test Agent Code Directly

```bash
cd agents_catalog/standalone_agents/XX-agent-name
python agent.py
```

Add a test block to your agent:

```python
# agent.py
from strands import Agent

agent = Agent(name="my-agent")

@agent.tool()
def my_tool(param: str) -> str:
    return f"Result: {param}"

if __name__ == "__main__":
    # Test your agent locally
    print("Testing agent...")
    response = agent.run("Test my_tool with param='hello'")
    print(f"Response: {response}")
```

### Test with Mock AWS Resources

Use `moto` to mock AWS services:

```bash
pip install moto[dynamodb,s3]
```

```python
# test_agent.py
from moto import mock_dynamodb
import boto3

@mock_dynamodb
def test_agent_with_dynamodb():
    # Create mock table
    dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
    table = dynamodb.create_table(
        TableName='MyAgent_Data',
        KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST'
    )
    
    # Test your agent's DynamoDB operations
    table.put_item(Item={'id': 'test', 'value': 'data'})
    response = table.get_item(Key={'id': 'test'})
    assert response['Item']['value'] == 'data'
```

## Testing in AWS

### Deploy and Test in UI

```bash
./deploy_cdk.sh
```

Then:
1. Open the UI URL from deployment output
2. Select your agent
3. Send test messages
4. Verify responses and trace steps

### Check CloudWatch Logs

```bash
# View agent logs
aws logs tail /aws/bedrock-agentcore/your-agent --follow

# View specific log stream
aws logs get-log-events \
  --log-group-name /aws/bedrock-agentcore/your-agent \
  --log-stream-name <stream-name>
```

### Test DynamoDB Access

Verify your agent can access tables:

```bash
# Check if table exists
aws dynamodb describe-table --table-name MyAgent_Data

# Scan table contents
aws dynamodb scan --table-name MyAgent_Data

# Check IAM permissions
aws iam get-role-policy \
  --role-name MA3TMainStack-IAMAgentRole* \
  --policy-name <policy-name>
```

## Common Test Cases

### Test Tool Execution

```python
if __name__ == "__main__":
    # Test each tool individually
    print("Testing store_data...")
    result = store_data("key1", "value1")
    print(f"Store result: {result}")
    
    print("Testing get_data...")
    result = get_data("key1")
    print(f"Get result: {result}")
```

### Test Error Handling

```python
@agent.tool()
def my_tool(param: str) -> str:
    try:
        # Your logic
        return result
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    # Test error case
    result = my_tool("invalid")
    assert "Error" in result
```

### Test with Real AWS (Integration Test)

```python
# test_integration.py
import boto3
import os

def test_real_dynamodb():
    """Test against real AWS resources"""
    table_name = os.environ.get('TABLE_NAME', 'MyAgent_Data')
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    
    # Test write
    table.put_item(Item={'id': 'test-123', 'value': 'test-data'})
    
    # Test read
    response = table.get_item(Key={'id': 'test-123'})
    assert response['Item']['value'] == 'test-data'
    
    # Cleanup
    table.delete_item(Key={'id': 'test-123'})
    print("Integration test passed!")

if __name__ == "__main__":
    test_real_dynamodb()
```

## Debugging

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

@agent.tool()
def my_tool(param: str) -> str:
    logging.debug(f"Tool called with: {param}")
    result = process(param)
    logging.debug(f"Tool returning: {result}")
    return result
```

### Check Agent Response Format

The UI expects responses in specific formats. Test your agent returns valid JSON:

```python
if __name__ == "__main__":
    response = agent.run("test")
    print(f"Response type: {type(response)}")
    print(f"Response: {response}")
    
    # Should be a string, not a dict
    assert isinstance(response, str)
```

### Verify AWS Credentials

```bash
# Check credentials work
aws sts get-caller-identity

# Test DynamoDB access
aws dynamodb list-tables
```

## Next Steps

- [Deployment Guide](deployment.md) - Deploy your tested agent
- [Troubleshooting](troubleshooting.md) - Debug issues
- [Infrastructure Setup](infrastructure-setup.md) - Add AWS resources
