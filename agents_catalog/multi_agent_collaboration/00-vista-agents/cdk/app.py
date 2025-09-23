#!/usr/bin/env python3
"""
Vehicle Service Management CDK App
Multi-Agent Collaboration with Supervisor Routing

This file exports the VistaServiceStack class for use as a nested stack.
When used as a nested stack, the main stack will import and instantiate this class.
"""

import os
import boto3
import aws_cdk as cdk
from constructs import Construct
from vista_service_stack import VistaServiceStack
from typing import Dict, Any, Optional

# Export the stack class for nested stack usage
__all__ = ['VistaServiceStack']

def get_aws_account():
    """Automatically detect AWS account ID"""
    try:
        # Get account from STS
        sts_client = boto3.client('sts')
        caller_identity = sts_client.get_caller_identity()
        account = caller_identity['Account']
        
        print(f"✅ Detected AWS Account: {account}")
        return account
        
    except Exception as e:
        print(f"❌ Error detecting AWS credentials: {e}")
        print("💡 Please ensure AWS credentials are configured:")
        print("   - Run 'aws configure' or")
        print("   - Set AWS_PROFILE environment variable or")
        print("   - Configure IAM role/instance profile")
        raise

def get_deployment_region():
    """Get region from CDK deployment parameters (single source of truth)"""
    import sys
    
    # Check command line arguments for region
    region_from_cli = None
    if '--region' in sys.argv:
        region_index = sys.argv.index('--region')
        if region_index + 1 < len(sys.argv):
            region_from_cli = sys.argv[region_index + 1]
    
    # Check for explicit region override
    explicit_region = os.environ.get('VISTA_DEPLOY_REGION')
    
    # Debug environment variables
    cdk_region = os.environ.get('CDK_DEFAULT_REGION')
    aws_region = os.environ.get('AWS_REGION') 
    aws_default_region = os.environ.get('AWS_DEFAULT_REGION')
    boto3_region = boto3.Session().region_name
    
    print(f"🔍 Debug - CLI region: {region_from_cli}")
    print(f"🔍 Debug - VISTA_DEPLOY_REGION: {explicit_region}")
    print(f"🔍 Debug - CDK_DEFAULT_REGION: {cdk_region}")
    print(f"🔍 Debug - AWS_REGION: {aws_region}")
    print(f"🔍 Debug - AWS_DEFAULT_REGION: {aws_default_region}")
    print(f"🔍 Debug - boto3.Session().region_name: {boto3_region}")
    
    # Region priority: CLI > explicit override > CDK_DEFAULT_REGION > AWS_REGION > AWS_DEFAULT_REGION > boto3 default > fallback
    region = region_from_cli or explicit_region or cdk_region or aws_region or aws_default_region or boto3_region or 'us-east-1'
    
    print(f"✅ Using Deployment Region: {region}")
    return region

def get_foundation_model():
    """Get foundation model from environment variables or use default"""
    import sys
    
    # Check command line arguments for foundation model
    model_from_cli = None
    if '--foundation-model' in sys.argv:
        model_index = sys.argv.index('--foundation-model')
        if model_index + 1 < len(sys.argv):
            model_from_cli = sys.argv[model_index + 1]
    
    # Check environment variable
    model_from_env = os.environ.get('VISTA_FOUNDATION_MODEL')
    
    # Use CLI > environment > default
    foundation_model = model_from_cli or model_from_env or "anthropic.claude-3-haiku-20240307-v1:0"
    
    print(f"🤖 Using Foundation Model: {foundation_model}")
    return foundation_model

class VistaServiceApp(cdk.App):
    """
    Standalone CDK app for Vista agents.
    This is used when deploying Vista agents independently.
    When used as a nested stack, the VistaServiceStack class is imported directly.
    """
    def __init__(self):
        super().__init__()
        
        # Automatically detect AWS account
        account = get_aws_account()
        
        # Get region from deployment parameters (single source of truth)
        region = get_deployment_region()
        
        # Get foundation model
        foundation_model = get_foundation_model()
        
        # Allow account override if needed
        account = os.environ.get('CDK_DEFAULT_ACCOUNT', account)
        # Note: region is already determined by get_deployment_region() which checks CDK_DEFAULT_REGION
        
        print(f"🚀 Deploying to Account: {account}, Region: {region}")
        
        # Create the main stack (standalone mode)
        VistaServiceStack(
            self, 
            "VistaServiceStack",
            foundation_model=foundation_model,
            env=cdk.Environment(account=account, region=region),
            description="Vehicle Service Management System - Multi-Agent Collaboration with Supervisor Routing"
        )

# Only run as standalone app if this file is executed directly
if __name__ == "__main__":
    # Create and synthesize the app
    app = VistaServiceApp()
    app.synth()
