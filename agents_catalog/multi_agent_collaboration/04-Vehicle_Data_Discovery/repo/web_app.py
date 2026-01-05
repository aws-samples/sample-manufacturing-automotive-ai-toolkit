#!/usr/bin/env python3
"""
Tesla Fleet Discovery Studio - Web Stack CDK App
Entry point for deploying the web components separately from the main pipeline
"""

import aws_cdk as cdk
from web_stack import TeslaWebStack

app = cdk.App()

# Deploy web stack to us-west-2 (same region as main pipeline)
TeslaWebStack(
    app,
    "TeslaWebStack",
    env=cdk.Environment(
        account='757513153970',  # Same account as main pipeline
        region='us-west-2'
    )
)

app.synth()