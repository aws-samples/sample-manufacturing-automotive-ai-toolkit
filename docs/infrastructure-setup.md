# Infrastructure Setup

This guide explains when and how to add AWS infrastructure to your agents.

## When Do You Need Infrastructure?

### Bedrock Agents
**Always required** - CDK creates the Bedrock agent resources.

### AgentCore Agents
**Optional** - Only needed when your agent requires:
- DynamoDB tables for data storage
- S3 buckets for file storage
- Lambda functions for external APIs
- Other AWS resources

## Creating a CDK Stack

### Step 1: Add Infrastructure to manifest.json

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

### Step 2: Create cdk/stack.py

```python
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
        
        # Create your AWS resources
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
```

**That's it!** The framework automatically grants permissions.

## Auto-Granted Permissions

The framework automatically grants the shared agent role access to:

### DynamoDB Tables
All tables created in your stack get automatic read/write access.

### S3 Buckets
All buckets created in your stack get automatic read/write access.

### How It Works
The framework:
1. Scans your stack after creation
2. Finds all DynamoDB tables and S3 buckets
3. Calls `.grant_read_write_data()` or `.grant_read_write()`
4. No manual permission management needed

## Common Resources

### DynamoDB Table

```python
self.table = dynamodb.Table(
    self, "DataTable",
    table_name="MyAgent_Data",
    partition_key=dynamodb.Attribute(
        name="id",
        type=dynamodb.AttributeType.STRING
    ),
    billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
    removal_policy=RemovalPolicy.DESTROY,
    point_in_time_recovery=True
)
```

### S3 Bucket

```python
from aws_cdk import aws_s3 as s3

self.bucket = s3.Bucket(
    self, "DataBucket",
    bucket_name=f"my-agent-data-{Stack.of(self).account}",
    removal_policy=RemovalPolicy.DESTROY,
    auto_delete_objects=True
)
```

### Lambda Function

```python
from aws_cdk import aws_lambda as lambda_

self.function = lambda_.Function(
    self, "ApiFunction",
    runtime=lambda_.Runtime.PYTHON_3_11,
    handler="index.handler",
    code=lambda_.Code.from_asset("lambda"),
    environment={
        "TABLE_NAME": self.table.table_name
    }
)

# Grant Lambda access to DynamoDB
self.table.grant_read_write_data(self.function)
```

## Custom Permissions

If you need permissions beyond DynamoDB/S3:

```python
from aws_cdk import aws_iam as iam

class MyAgentStack(NestedStack):
    def __init__(self, scope, construct_id, shared_resources=None, **kwargs):
        super().__init__(scope, construct_id, shared_resources, **kwargs)
        
        # Create resources (auto-granted)
        self.table = dynamodb.Table(...)
        
        # Add custom permissions
        if shared_resources and 'agent_role' in shared_resources:
            shared_resources['agent_role'].add_to_policy(
                iam.PolicyStatement(
                    actions=["secretsmanager:GetSecretValue"],
                    resources=[
                        f"arn:aws:secretsmanager:{Stack.of(self).region}:"
                        f"{Stack.of(self).account}:secret:my-secret-*"
                    ]
                )
            )
```

## Accessing Resources in Your Agent

Use boto3 to access your resources:

```python
# agent.py
import boto3
from strands import Agent

agent = Agent(name="my-agent")
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('MyAgent_Data')

@agent.tool()
def store_data(key: str, value: str) -> str:
    """Store data in DynamoDB"""
    table.put_item(Item={'id': key, 'value': value})
    return f"Stored {key}"

@agent.tool()
def get_data(key: str) -> str:
    """Get data from DynamoDB"""
    response = table.get_item(Key={'id': key})
    return response.get('Item', {}).get('value', 'Not found')
```

## Stack Outputs

Export values for reference:

```python
from aws_cdk import CfnOutput

CfnOutput(
    self, "TableName",
    value=self.table.table_name,
    description="DynamoDB table name"
)

CfnOutput(
    self, "BucketName",
    value=self.bucket.bucket_name,
    description="S3 bucket name"
)
```

## Best Practices

### Use RemovalPolicy.DESTROY for Development
```python
removal_policy=RemovalPolicy.DESTROY
```
This allows easy cleanup during development.

### Use Specific Resource Names
```python
table_name=f"MyAgent_Data_{Stack.of(self).region}"
```
Avoid conflicts across regions.

### Enable Point-in-Time Recovery
```python
point_in_time_recovery=True
```
For production DynamoDB tables.

### Use Environment Variables
Pass resource names to your agent:

```python
# In stack
CfnOutput(self, "TableName", value=self.table.table_name)

# In agent
import os
table_name = os.environ.get('TABLE_NAME', 'MyAgent_Data')
```

## Troubleshooting

### "Table not found" errors
- Ensure table name matches between CDK and agent code
- Check CloudFormation outputs for actual table name

### Permission denied errors
- Verify resource is created in your stack
- Check if resource type is auto-granted (DynamoDB, S3)
- Add custom permissions if needed

### Stack deployment fails
- Verify CDK syntax
- Check for resource name conflicts
- Ensure AWS credentials are configured

## Next Steps

- [Adding Agents](adding-agents.md) - Create your first agent
- [Manifest Configuration](manifest-configuration.md) - Configure infrastructure
- [Testing Agents](testing-agents.md) - Test your infrastructure
