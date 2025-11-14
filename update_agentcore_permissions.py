#!/usr/bin/env python3

import boto3
import json
import sys

def get_boto3_client(service_name, region_name='us-east-1'):
    """Get boto3 client with profile support"""
    try:
        session = boto3.Session(profile_name='grantaws')
        return session.client(service_name, region_name=region_name)
    except:
        return boto3.client(service_name, region_name=region_name)

def load_manifest_permissions():
    """Load runtime permissions from manifest.json"""
    manifest_path = "agents_catalog/multi_agent_collaboration/02-quality_inspection_agentcore/manifest.json"
    
    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        permissions = manifest.get('agentcore', {}).get('runtime_permissions', [])
        if not permissions:
            print("❌ No runtime_permissions found in manifest")
            return None
        
        print(f"✅ Loaded {len(permissions)} permissions from manifest")
        return permissions
    
    except Exception as e:
        print(f"❌ Error loading manifest: {e}")
        return None

def get_agentcore_runtime_arns():
    """Get all AgentCore runtime ARNs from SSM parameters"""
    ssm = get_boto3_client('ssm')
    
    try:
        response = ssm.get_parameters_by_path(
            Path='/quality-inspection/agentcore-runtime',
            Recursive=True
        )
        
        runtime_arns = {}
        for param in response['Parameters']:
            agent_name = param['Name'].split('/')[-1]
            runtime_arns[agent_name] = param['Value']
        
        print(f"✅ Found {len(runtime_arns)} AgentCore runtime ARNs")
        return runtime_arns
    
    except Exception as e:
        print(f"❌ Error getting runtime ARNs: {e}")
        return {}

def get_agentcore_runtime_roles():
    """Get all AgentCore runtime role names"""
    iam = get_boto3_client('iam')
    
    try:
        response = iam.list_roles()
        runtime_roles = []
        
        for role in response['Roles']:
            role_name = role['RoleName']
            if role_name.startswith('AmazonBedrockAgentCoreSDKRuntime-'):
                runtime_roles.append(role_name)
        
        print(f"✅ Found {len(runtime_roles)} AgentCore runtime roles")
        return runtime_roles
    
    except Exception as e:
        print(f"❌ Error getting runtime roles: {e}")
        return []

def create_policy_document(permissions, resources):
    """Create IAM policy document from permissions list"""
    
    # Group permissions by service for better organization
    statements = []
    
    # ECR permissions
    ecr_actions = [p for p in permissions if p.startswith('ecr:')]
    if ecr_actions:
        statements.append({
            "Effect": "Allow",
            "Action": ecr_actions,
            "Resource": "*"
        })
    
    # DynamoDB permissions
    dynamodb_actions = [p for p in permissions if p.startswith('dynamodb:')]
    if dynamodb_actions:
        statements.append({
            "Effect": "Allow", 
            "Action": dynamodb_actions,
            "Resource": resources.get('dynamodb_table_arn', '*')
        })
    
    # S3 permissions
    s3_actions = [p for p in permissions if p.startswith('s3:')]
    if s3_actions:
        bucket_arn = resources.get('s3_bucket_arn')
        if bucket_arn and bucket_arn != '*':
            s3_resources = [bucket_arn, f"{bucket_arn}/*"]
        else:
            s3_resources = "*"
        
        statements.append({
            "Effect": "Allow",
            "Action": s3_actions, 
            "Resource": s3_resources
        })
    
    # SNS permissions
    sns_actions = [p for p in permissions if p.startswith('sns:')]
    if sns_actions:
        statements.append({
            "Effect": "Allow",
            "Action": sns_actions,
            "Resource": resources.get('sns_topic_arn', '*')
        })
    
    # SSM permissions
    ssm_actions = [p for p in permissions if p.startswith('ssm:')]
    if ssm_actions:
        statements.append({
            "Effect": "Allow",
            "Action": ssm_actions,
            "Resource": "*"
        })
    
    # Bedrock permissions
    bedrock_actions = [p for p in permissions if p.startswith('bedrock')]
    if bedrock_actions:
        statements.append({
            "Effect": "Allow",
            "Action": bedrock_actions,
            "Resource": "*"
        })
    
    # STS permissions
    sts_actions = [p for p in permissions if p.startswith('sts:')]
    if sts_actions:
        statements.append({
            "Effect": "Allow",
            "Action": sts_actions,
            "Resource": "*"
        })
    
    # CloudWatch Logs permissions
    logs_actions = [p for p in permissions if p.startswith('logs:')]
    if logs_actions:
        statements.append({
            "Effect": "Allow",
            "Action": logs_actions,
            "Resource": "*"
        })
    
    return {
        "Version": "2012-10-17",
        "Statement": statements
    }

def get_stack_resources():
    """Get resource ARNs from CloudFormation stack"""
    cf = get_boto3_client('cloudformation')
    
    resources = {}
    try:
        # Try to get resources from MA3TMainStack
        response = cf.describe_stacks(StackName='MA3TMainStack')
        outputs = response['Stacks'][0].get('Outputs', [])
        
        for output in outputs:
            key = output['OutputKey'].lower()
            if 'dynamodb' in key or 'table' in key:
                resources['dynamodb_table_arn'] = output['OutputValue']
            elif 'bucket' in key and 's3' in key:
                resources['s3_bucket_arn'] = f"arn:aws:s3:::{output['OutputValue']}"
            elif 'sns' in key or 'topic' in key:
                resources['sns_topic_arn'] = output['OutputValue']
    
    except Exception as e:
        print(f"⚠️ Could not get stack resources: {e}")
    
    return resources

def update_role_policy(role_name, policy_document):
    """Update IAM role with new inline policy"""
    iam = get_boto3_client('iam')
    
    try:
        # Put the inline policy
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName='AgentCoreRuntimePermissions',
            PolicyDocument=json.dumps(policy_document, indent=2)
        )
        print(f"✅ Updated policy for role: {role_name}")
        return True
    
    except Exception as e:
        print(f"❌ Failed to update role {role_name}: {e}")
        return False

def main():
    print("🔧 Updating AgentCore Runtime Role Permissions")
    print("=" * 50)
    
    # Load permissions from manifest
    permissions = load_manifest_permissions()
    if not permissions:
        sys.exit(1)
    
    # Get runtime ARNs
    runtime_arns = get_agentcore_runtime_arns()
    if not runtime_arns:
        sys.exit(1)
    
    # Get stack resources for ARNs
    resources = get_stack_resources()
    
    # Create policy document
    policy_document = create_policy_document(permissions, resources)
    
    print(f"\n📋 Policy document created with {len(policy_document['Statement'])} statements")
    
    # Get runtime roles
    runtime_roles = get_agentcore_runtime_roles()
    if not runtime_roles:
        print("❌ No AgentCore runtime roles found")
        sys.exit(1)
    
    # Update each role
    success_count = 0
    for role_name in runtime_roles:
        print(f"\n🔄 Updating role: {role_name}")
        if update_role_policy(role_name, policy_document):
            success_count += 1
    
    print(f"\n✅ Successfully updated {success_count}/{len(runtime_roles)} roles")
    
    if success_count == len(runtime_roles):
        print("🎉 All AgentCore runtime roles updated successfully!")
        return 0
    else:
        print("⚠️ Some roles failed to update")
        return 1

if __name__ == "__main__":
    sys.exit(main())