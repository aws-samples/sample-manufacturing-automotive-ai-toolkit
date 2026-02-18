#!/usr/bin/env python3
"""
CDK Stack for SFC Config Agent Infrastructure
Creates S3 bucket and DynamoDB table for persisting agent-generated files.
"""

from aws_cdk import (
    NestedStack,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_ssm as ssm,
    RemovalPolicy,
    CfnOutput,
)
from cdk_nag import NagSuppressions
from constructs import Construct


class SfcConfigAgentStack(NestedStack):
    """
    Infrastructure stack for the SFC Config Agent.

    Provides:
    - S3 bucket for storing all agent-generated files (configs, results, conversations)
    - DynamoDB table for file metadata index + base64-encoded content cache
    """

    def __init__(self, scope: Construct, construct_id: str, shared_resources=None, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # ----------------------------------------------------------------
        # S3 Bucket — stores all agent-generated files
        # ----------------------------------------------------------------
        self.artifacts_bucket = s3.Bucket(
            self, "SfcAgentArtifactsBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            enforce_ssl=True,
            versioned=False,
        )

        # ----------------------------------------------------------------
        # DynamoDB Table — file metadata index + base64 content cache
        # PK: file_type (config | result | conversation | run)
        # SK: created_at#file_key (e.g. "2026-02-18T10:45:30Z#configs/my-config.json")
        # ----------------------------------------------------------------
        self.files_table = dynamodb.Table(
            self, "SfcAgentFilesTable",
            table_name="SFC_Agent_Files",
            partition_key=dynamodb.Attribute(
                name="file_type",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="sort_key",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True,
        )

        # ----------------------------------------------------------------
        # CDK-Nag Suppressions
        # ----------------------------------------------------------------
        NagSuppressions.add_resource_suppressions(
            self.artifacts_bucket,
            [
                {
                    "id": "AwsSolutions-S1",
                    "reason": "Server access logging not required for this demo/internal artifacts bucket.",
                },
            ],
        )

        # ----------------------------------------------------------------
        # SSM Parameters — allow agent to discover resources at runtime
        # (same pattern as 03-quality-inspection)
        # ----------------------------------------------------------------
        ssm.StringParameter(
            self, "SfcS3BucketNameParameter",
            parameter_name="/sfc-config-agent/s3-bucket-name",
            string_value=self.artifacts_bucket.bucket_name,
            description="S3 bucket name for SFC Config Agent artifacts",
        )

        ssm.StringParameter(
            self, "SfcDdbTableNameParameter",
            parameter_name="/sfc-config-agent/ddb-table-name",
            string_value=self.files_table.table_name,
            description="DynamoDB table name for SFC Config Agent file metadata",
        )

        # ----------------------------------------------------------------
        # Outputs
        # ----------------------------------------------------------------
        CfnOutput(
            self, "SfcArtifactsBucketName",
            value=self.artifacts_bucket.bucket_name,
            description="S3 bucket for SFC agent artifacts",
        )
        CfnOutput(
            self, "SfcFilesTableName",
            value=self.files_table.table_name,
            description="DynamoDB table for SFC agent file metadata",
        )
