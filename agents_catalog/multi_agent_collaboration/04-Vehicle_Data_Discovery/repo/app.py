#!/usr/bin/env python3
import os
import aws_cdk as cdk
from tesla_fleet_discovery_cdk_stack import TeslaFleetDiscoveryCdkStack

app = cdk.App()

# --- Tesla Fleet Discovery Stack ---
# When run standalone, uses CDK_DEFAULT_ACCOUNT/REGION from environment
# When deployed via main stack, runs as a NestedStack
TeslaFleetDiscoveryCdkStack(app, "TeslaFleetDiscoveryStack",
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'),
        region=os.getenv('CDK_DEFAULT_REGION', 'us-west-2')
    ),
)

app.synth()
