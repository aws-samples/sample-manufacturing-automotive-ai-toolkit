#!/usr/bin/env python3
"""
Manufacturing & Automotive AI Toolkit (MA3T) CDK App
Main entry point for CDK deployment
"""

import os
import aws_cdk as cdk
from stacks.main_stack import MainStack

app = cdk.App()

# Get environment from CDK context or environment variables
account = app.node.try_get_context("account") or os.environ.get("CDK_DEFAULT_ACCOUNT")
region = app.node.try_get_context("region") or os.environ.get("CDK_DEFAULT_REGION") or "us-west-2"

# Create the main stack with explicit environment
MainStack(
    app, 
    "MA3TMainStack",
    description="Manufacturing & Automotive AI Toolkit - Main Infrastructure Stack",
    env=cdk.Environment(account=account, region=region)
)

app.synth()