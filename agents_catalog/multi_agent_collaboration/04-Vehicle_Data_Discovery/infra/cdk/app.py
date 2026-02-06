#!/usr/bin/env python3
import os
import aws_cdk as cdk
from aws_cdk import Stack
from fleet_discovery_cdk_stack import FleetDiscoveryCdkStack

class StandaloneFleetDiscoveryStack(Stack):
    """Wrapper stack for standalone deployment of Fleet Discovery"""
    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        FleetDiscoveryCdkStack(self, "FleetDiscovery", shared_resources={})

app = cdk.App()
StandaloneFleetDiscoveryStack(app, "FleetDiscoveryStack",
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'),
        region=os.getenv('CDK_DEFAULT_REGION', 'us-west-2')
    ),
)
app.synth()
