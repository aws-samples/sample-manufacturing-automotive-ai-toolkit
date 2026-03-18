"""
WP-01: DynamoDB tables for the SFC Control Plane.

Creates:
  - LaunchPackageTable  (PK: packageId, SK: createdAt, GSI: configId-index)
  - ControlPlaneStateTable (PK: stateKey — singleton "global")
"""

from aws_cdk import (
    CfnOutput,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
)
from constructs import Construct


class LaunchPackageTables(Construct):
    """CDK construct that provisions the two new Control Plane DynamoDB tables."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ----------------------------------------------------------------
        # LaunchPackageTable
        # PK: packageId (S)   SK: createdAt (S)
        # GSI: configId-index  PK: configId
        # ----------------------------------------------------------------
        self.launch_package_table = dynamodb.Table(
            self,
            "LaunchPackageTable",
            table_name="SFC_Launch_Packages",
            partition_key=dynamodb.Attribute(
                name="packageId",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="createdAt",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True,
        )

        # GSI: look up packages by configId
        self.launch_package_table.add_global_secondary_index(
            index_name="configId-index",
            partition_key=dynamodb.Attribute(
                name="configId",
                type=dynamodb.AttributeType.STRING,
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # ----------------------------------------------------------------
        # ControlPlaneStateTable
        # PK: stateKey (S) — singleton item, always "global"
        # ----------------------------------------------------------------
        self.control_plane_state_table = dynamodb.Table(
            self,
            "ControlPlaneStateTable",
            table_name="SFC_ControlPlane_State",
            partition_key=dynamodb.Attribute(
                name="stateKey",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True,
        )

        # ----------------------------------------------------------------
        # CFN Outputs
        # ----------------------------------------------------------------
        CfnOutput(
            self,
            "LaunchPackageTableName",
            value=self.launch_package_table.table_name,
            description="DynamoDB table for SFC Launch Packages",
        )
        CfnOutput(
            self,
            "LaunchPackageTableArn",
            value=self.launch_package_table.table_arn,
            description="DynamoDB table ARN for SFC Launch Packages",
        )
        CfnOutput(
            self,
            "ControlPlaneStateTableName",
            value=self.control_plane_state_table.table_name,
            description="DynamoDB singleton state table for SFC Control Plane",
        )
        CfnOutput(
            self,
            "ControlPlaneStateTableArn",
            value=self.control_plane_state_table.table_arn,
            description="DynamoDB singleton state table ARN for SFC Control Plane",
        )