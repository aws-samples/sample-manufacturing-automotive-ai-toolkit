#!/usr/bin/env python3

import aws_cdk as cdk
from cloudfront_stack import TeslaCloudFrontStack

app = cdk.App()

# CloudFront Distribution Stack for path-based routing
cloudfront_stack = TeslaCloudFrontStack(
    app,
    "TeslaCloudFrontStack",
    env=cdk.Environment(
        account="757513153970",
        region="us-east-1"  # CloudFront certificates must be in us-east-1
    )
)

app.synth()