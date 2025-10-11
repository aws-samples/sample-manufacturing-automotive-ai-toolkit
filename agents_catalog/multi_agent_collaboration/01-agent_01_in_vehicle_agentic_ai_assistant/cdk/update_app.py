#!/usr/bin/env python3
"""
CDK App for VISTA Agent Stack
"""

import aws_cdk as cdk
from updatestack import VistaAgentStack

app = cdk.App()

VistaAgentStack(
    app, 
    "VistaAgentStack",
    description="VISTA Agent DynamoDB Tables and IAM Roles"
)

app.synth()
