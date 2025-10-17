# Troubleshooting

Common issues and solutions when developing and deploying MA3T agents.

## Deployment Issues

### Stack Creation Failed

**Error**: CloudFormation stack creation failed

**Solutions**:
1. Check CloudFormation events in AWS Console
2. Look for specific error messages
3. Common causes:
   - Resource name conflicts
   - Insufficient permissions
   - Invalid resource configurations
   - Region not supported

**Fix**:
```bash
# View stack events
aws cloudformation describe-stack-events --stack-name MA3TMainStack

# Delete failed stack and retry
cdk destroy --context region=us-west-2
./deploy_cdk.sh
```

### AgentCore Deployment Failed

**Error**: CodeBuild project failed

**Solutions**:
1. Check CodeBuild logs in AWS Console
2. Common causes:
   - Docker build errors
   - Missing dependencies
   - Syntax errors in agent code
   - ECR push failures

**Fix**:
```bash
# Test Docker build locally
cd agents_catalog/standalone_agents/XX-agent-name
docker build -t test-agent .

# Check agent code
python agent.py

# Redeploy
./deploy_cdk.sh
```

### Permission Denied Errors

**Error**: `AccessDeniedException` or `User is not authorized`

**Solutions**:
1. Verify IAM role has correct permissions
2. Check if auto-grant framework ran
3. Ensure resource exists

**Fix**:
```python
# Add custom permissions if needed
if shared_resources and 'agent_role' in shared_resources:
    shared_resources['agent_role'].add_to_policy(
        iam.PolicyStatement(
            actions=["service:Action"],
            resources=["arn:aws:service:region:account:resource"]
        )
    )
```

## Agent Issues

### Agent Not Appearing in UI

**Causes**:
- `manifest.json` not found
- Invalid manifest format
- Agent not deployed

**Fix**:
1. Verify `manifest.json` exists
2. Validate JSON syntax
3. Check agent was discovered:
```bash
# Look for discovery logs during deployment
./deploy_cdk.sh | grep "Discovered"
```

### Agent Not Responding

**Causes**:
- Agent code errors
- Missing dependencies
- AWS resource not accessible

**Fix**:
1. Check CloudWatch logs
2. Test agent locally:
```bash
cd agents_catalog/standalone_agents/XX-agent-name
python agent.py
```
3. Verify AWS resources exist

### Tool Execution Fails

**Causes**:
- Tool code errors
- Missing permissions
- Invalid parameters

**Fix**:
```python
# Add error handling
@agent.tool()
def my_tool(param: str) -> str:
    try:
        # Tool logic
        return result
    except Exception as e:
        logger.error(f"Tool error: {e}")
        return f"Error: {str(e)}"
```

## Infrastructure Issues

### DynamoDB Table Not Found

**Error**: `ResourceNotFoundException`

**Solutions**:
1. Verify table was created in CDK stack
2. Check table name matches
3. Ensure stack deployed successfully

**Fix**:
```python
# Use environment variable for table name
import os
table_name = os.environ.get('TABLE_NAME', 'Default_Table_Name')
table = dynamodb.Table(table_name)
```

### S3 Access Denied

**Error**: `AccessDenied` when accessing S3

**Solutions**:
1. Verify bucket exists
2. Check auto-grant ran
3. Verify bucket name

**Fix**:
```python
# Check bucket exists
import boto3
s3 = boto3.client('s3')
try:
    s3.head_bucket(Bucket='my-bucket')
except Exception as e:
    print(f"Bucket error: {e}")
```

### Lambda Function Timeout

**Error**: Lambda function times out

**Solutions**:
1. Increase timeout in CDK
2. Optimize function code
3. Check for infinite loops

**Fix**:
```python
self.function = lambda_.Function(
    self, "Function",
    timeout=Duration.seconds(300),  # Increase timeout
    memory_size=512  # Increase memory
)
```

## Manifest Issues

### Invalid Agent ID

**Error**: `Agent ID validation failed`

**Rules**:
- Must start with a letter
- Only alphanumeric and underscores
- Maximum 48 characters

**Fix**:
```json
{
  "id": "my_agent_123",  // Valid
  "id": "123_agent",     // Invalid - starts with number
  "id": "my-agent",      // Invalid - contains hyphen
}
```

### Missing Required Fields

**Error**: `Missing required field`

**Required fields**:
- `id`
- `name`
- `type`

**Fix**:
```json
{
  "agents": [{
    "id": "my_agent",
    "name": "My Agent",
    "type": "agentcore"
  }]
}
```

### Stack Class Not Found

**Error**: `Could not import stack class`

**Solutions**:
1. Verify `stack_class` matches class name in file
2. Check `stack_path` is correct
3. Ensure file exists

**Fix**:
```json
{
  "infrastructure": {
    "cdk": true,
    "stack_class": "MyAgentStack",  // Must match class name
    "stack_path": "cdk/stack.py"    // Must exist
  }
}
```

## UI Issues

### UI Not Loading

**Causes**:
- App Runner service not started
- Authentication failed
- Network issues

**Fix**:
1. Check App Runner service status in AWS Console
2. Verify authentication credentials
3. Check security group rules

### Authentication Failed

**Error**: `401 Unauthorized`

**Solutions**:
1. Verify username and password
2. Check they match deployment parameters
3. Clear browser cache

**Fix**:
```bash
# Redeploy with correct credentials
./deploy_cdk.sh --auth-user admin --auth-password newpassword
```

## Development Issues

### Local Testing Fails

**Causes**:
- Missing dependencies
- AWS credentials not configured
- Import errors

**Fix**:
```bash
# Install dependencies
pip install -r requirements.txt

# Configure AWS credentials
aws configure

# Test imports
python -c "from agent import agent; print(agent)"
```

### Docker Build Fails

**Causes**:
- Missing Dockerfile
- Invalid Dockerfile syntax
- Dependency installation errors

**Fix**:
```bash
# Test build locally
docker build -t test-agent .

# Check logs for errors
docker build -t test-agent . 2>&1 | tee build.log
```

### Import Errors

**Error**: `ModuleNotFoundError`

**Solutions**:
1. Install missing package
2. Add to `requirements.txt`
3. Verify package name

**Fix**:
```bash
# Install package
pip install package-name

# Add to requirements.txt
echo "package-name>=1.0.0" >> requirements.txt
```

## Getting Help

### Check Logs

**CloudWatch Logs**:
```
AWS Console → CloudWatch → Log groups → /aws/bedrock-agentcore/
```

**CodeBuild Logs**:
```
AWS Console → CodeBuild → Build history
```

**App Runner Logs**:
```
AWS Console → App Runner → Service → Logs
```

### Debug Mode

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Community Support

1. Check existing agents for examples
2. Review documentation
3. Open GitHub issue
4. Search CloudFormation events

## Common Error Messages

### "Resource already exists"
**Solution**: Delete existing resource or use unique name

### "Rate exceeded"
**Solution**: Wait and retry, or request limit increase

### "Invalid parameter"
**Solution**: Check parameter format and constraints

### "Insufficient capacity"
**Solution**: Try different region or wait and retry

## Next Steps

- [Adding Agents](adding-agents.md) - Create agents correctly
- [Infrastructure Setup](infrastructure-setup.md) - Configure resources properly
- [Testing Agents](testing-agents.md) - Test before deploying
- [Deployment Guide](deployment.md) - Deploy successfully
