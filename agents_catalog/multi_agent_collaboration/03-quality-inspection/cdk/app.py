#!/usr/bin/env python3
import aws_cdk as cdk
import os
from quality_inspection_stack import QualityInspectionStack

app = cdk.App()

# Use current AWS account and region from profile/environment
# This makes the stack deployable to any account
env = cdk.Environment(
    account=os.environ.get('CDK_DEFAULT_ACCOUNT'),
    region=os.environ.get('CDK_DEFAULT_REGION', 'us-east-1')
)

# Get optional existing VPC ID from context
existing_vpc_id = app.node.try_get_context("existing_vpc_id")

# Main infrastructure stack
main_stack = QualityInspectionStack(
    app, 
    "AgenticQualityInspectionStack", 
    existing_vpc_id=existing_vpc_id,
    env=env
)

app.synth()