"""
Common CDK-Nag suppressions for MA3T
Use this file to centrally manage suppressions across all stacks
"""

from cdk_nag import NagSuppressions
from aws_cdk import Stack

def apply_common_suppressions(stack: Stack):
    """Apply common suppressions that are acceptable for MA3T use cases"""
    
    # Common suppressions for development/demo environments
    common_suppressions = [
        {
            "id": "AwsSolutions-IAM4",
            "reason": "AWS managed policies are acceptable for demo/development environments"
        },
        {
            "id": "AwsSolutions-IAM5", 
            "reason": "Wildcard permissions may be needed for Bedrock agents and dynamic resources"
        },
        {
            "id": "AwsSolutions-L1",
            "reason": "Lambda runtime versions are managed by CDK defaults"
        },
        {
            "id": "AwsSolutions-S1",
            "reason": "S3 access logging not required for demo buckets"
        },
        {
            "id": "AwsSolutions-CB4",
            "reason": "CodeBuild encryption with AWS managed keys is sufficient for demo"
        }
    ]
    
    # Apply suppressions to the entire stack
    NagSuppressions.add_stack_suppressions(stack, common_suppressions)

def apply_bedrock_suppressions(stack: Stack):
    """Apply suppressions specific to Bedrock agents"""
    
    bedrock_suppressions = [
        {
            "id": "AwsSolutions-IAM5",
            "reason": "Bedrock agents require broad permissions to access models and knowledge bases"
        },
        {
            "id": "AwsSolutions-IAM4", 
            "reason": "Bedrock service roles use AWS managed policies"
        }
    ]
    
    NagSuppressions.add_stack_suppressions(stack, bedrock_suppressions)

def apply_agentcore_suppressions(stack: Stack):
    """Apply suppressions specific to AgentCore containers"""
    
    agentcore_suppressions = [
        {
            "id": "AwsSolutions-ECS2",
            "reason": "Environment variables may contain configuration that appears sensitive"
        },
        {
            "id": "AwsSolutions-ECS4",
            "reason": "Container insights not required for demo environments"
        }
    ]
    
    NagSuppressions.add_stack_suppressions(stack, agentcore_suppressions)
