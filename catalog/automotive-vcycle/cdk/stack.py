#!/usr/bin/env python3
"""
CDK Nested Stack for Automotive V-Cycle Design Guidelines Infrastructure.

Creates:
- S3 bucket for design guidelines (versioned, encrypted, public access blocked)
- BucketDeployment to upload guideline markdown files from the project
- Lambda function for guideline retrieval (used by AgentCore Gateway)
- IAM role for AgentCore Gateway to invoke Lambda and read S3
- CfnOutputs for bucket name, Lambda ARN, and Gateway role ARN
"""

import os
import textwrap
from aws_cdk import (
    NestedStack,
    Stack,
    RemovalPolicy,
    CfnOutput,
    Duration,
    aws_s3 as s3,
    aws_s3_deployment as s3_deploy,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_bedrockagentcore as agentcore,
)
from constructs import Construct


class AutomotiveVCycleStack(NestedStack):
    """Nested stack for automotive V-cycle design guidelines infrastructure."""

    def __init__(self, scope: Construct, construct_id: str, shared_resources=None, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        shared_resources = shared_resources or {}

        # ----------------------------------------------------------------
        # S3 Access Logs Bucket
        # ----------------------------------------------------------------
        self.access_logs_bucket = s3.Bucket(
            self, "AccessLogsBucket",
            versioned=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            enforce_ssl=True,
        )

        # ----------------------------------------------------------------
        # S3 Bucket for design guidelines
        # ----------------------------------------------------------------
        self.guidelines_bucket = s3.Bucket(
            self, "DesignGuidelinesBucket",
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            server_access_logs_bucket=self.access_logs_bucket,
            server_access_logs_prefix="guidelines-access-logs/",
            enforce_ssl=True,
        )

        # ----------------------------------------------------------------
        # Upload guidelines/*.md from the project directory to S3
        # ----------------------------------------------------------------
        guidelines_path = os.path.join(os.path.dirname(__file__), "..", "guidelines")

        s3_deploy.BucketDeployment(
            self, "DeployGuidelines",
            sources=[s3_deploy.Source.asset(guidelines_path)],
            destination_bucket=self.guidelines_bucket,
        )

        # ----------------------------------------------------------------
        # Lambda function for guideline retrieval
        # ----------------------------------------------------------------
        self.guidelines_lambda = _lambda.Function(
            self, "DesignGuidelinesLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="index.lambda_handler",
            timeout=Duration.seconds(30),
            environment={
                "BUCKET_NAME": self.guidelines_bucket.bucket_name,
            },
            code=_lambda.Code.from_inline(LAMBDA_CODE),
        )

        # Grant Lambda read access to the guidelines bucket
        self.guidelines_bucket.grant_read(self.guidelines_lambda)

        # ----------------------------------------------------------------
        # IAM Role for AgentCore Gateway
        # ----------------------------------------------------------------
        self.gateway_role = iam.Role(
            self, "GatewayAgentCoreRole",
            assumed_by=iam.ServicePrincipal(
                "bedrock-agentcore.amazonaws.com",
                conditions={
                    "StringEquals": {
                        "aws:SourceAccount": Stack.of(self).account,
                    },
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{Stack.of(self).region}:{Stack.of(self).account}:*",
                    },
                },
            ),
        )

        # Allow Gateway role to invoke the Lambda function
        self.guidelines_lambda.grant_invoke(self.gateway_role)

        # Allow Gateway role to read from S3
        self.guidelines_bucket.grant_read(self.gateway_role)

        # Allow Gateway role bedrock-agentcore and bedrock actions
        self.gateway_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:*",
                    "bedrock:*",
                ],
                resources=["*"],
            )
        )

        # ----------------------------------------------------------------
        # Grant shared agent_role access if available
        # ----------------------------------------------------------------
        if shared_resources.get("agent_role"):
            self.guidelines_bucket.grant_read(shared_resources["agent_role"])
            self.guidelines_lambda.grant_invoke(shared_resources["agent_role"])

        # ----------------------------------------------------------------
        # AgentCore Gateway (MCP, CUSTOM_JWT auth via Gateway Cognito)
        # ----------------------------------------------------------------
        gw_discovery_url = shared_resources.get("gateway_cognito_discovery_url", "")
        gw_client_id = shared_resources.get("gateway_cognito_client_id", "")

        self.gateway = agentcore.CfnGateway(
            self, "DesignGuidesGateway",
            name="GuidelinesGateway",
            role_arn=self.gateway_role.role_arn,
            protocol_type="MCP",
            authorizer_type="CUSTOM_JWT",
            authorizer_configuration=agentcore.CfnGateway.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=agentcore.CfnGateway.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=gw_discovery_url,
                    allowed_clients=[gw_client_id] if gw_client_id else [],
                ),
            ),
            protocol_configuration=agentcore.CfnGateway.GatewayProtocolConfigurationProperty(
                mcp=agentcore.CfnGateway.MCPGatewayConfigurationProperty(
                    supported_versions=["2025-03-26"],
                ),
            ),
        )

        agentcore.CfnGatewayTarget(
            self, "GuidelinesTarget",
            gateway_identifier=self.gateway.ref,
            name="GuidelineLambdaTarget",
            credential_provider_configurations=[
                agentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE",
                ),
            ],
            target_configuration=agentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=agentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    lambda_=agentcore.CfnGatewayTarget.McpLambdaTargetConfigurationProperty(
                        lambda_arn=self.guidelines_lambda.function_arn,
                        tool_schema=agentcore.CfnGatewayTarget.ToolSchemaProperty(
                            inline_payload=[
                                agentcore.CfnGatewayTarget.ToolDefinitionProperty(
                                    name="get_technical_guideline",
                                    description="Retrieve technical design guideline",
                                    input_schema=agentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                                        type="object", properties={}, required=[],
                                    ),
                                ),
                                agentcore.CfnGatewayTarget.ToolDefinitionProperty(
                                    name="list_available_guidelines",
                                    description="List all available guideline files",
                                    input_schema=agentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                                        type="object", properties={}, required=[],
                                    ),
                                ),
                            ],
                        ),
                    ),
                ),
            ),
        )

        # ----------------------------------------------------------------
        # Outputs
        # ----------------------------------------------------------------
        CfnOutput(
            self, "GuidelinesBucketName",
            value=self.guidelines_bucket.bucket_name,
            description="S3 bucket containing design guidelines",
        )
        CfnOutput(
            self, "GuidelinesLambdaArn",
            value=self.guidelines_lambda.function_arn,
            description="Lambda function ARN for retrieving guidelines",
        )
        CfnOutput(
            self, "GatewayRoleArn",
            value=self.gateway_role.role_arn,
            description="IAM role ARN for AgentCore Gateway",
        )
        CfnOutput(
            self, "GatewayUrl",
            value=self.gateway.attr_gateway_url,
            description="AgentCore Gateway URL for MCP connections",
        )


# ---------------------------------------------------------------------------
# Inline Lambda code (same logic as original CFN DesignGuidelinesLambda)
# ---------------------------------------------------------------------------
LAMBDA_CODE = textwrap.dedent("""\
    import json
    import boto3
    import os
    from botocore.exceptions import ClientError

    s3_client = boto3.client('s3')

    def lambda_handler(event, context):
        print(f'Context: , {context.client_context}')
        print(f'Event: , {event}')

        try:
            toolName = context.client_context.custom['bedrockAgentCoreToolName']
            delimiter = "___"
            if delimiter in toolName:
                toolName = toolName[toolName.index(delimiter) + len(delimiter):]
            bucket_name = os.environ['BUCKET_NAME']

            if toolName == 'get_technical_guideline':
                return get_technical_guideline(bucket_name)
            elif toolName == 'list_available_guidelines':
                return list_available_guidelines(bucket_name)
            else:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Unknown tool name'})
                }

        except Exception as e:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': str(e)})
            }

    def get_technical_guideline(bucket_name, guideline_type=None):
        try:
            file_key = 'technical-design-guidelines.md'

            response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
            content = response['Body'].read().decode('utf-8')

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'content': content,
                    'file_key': file_key
                })
            }

        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return {
                    'statusCode': 404,
                    'body': json.dumps({'error': f'Guideline file not found: {file_key}'})
                }
            else:
                raise e

    def list_available_guidelines(bucket_name):
        try:
            response = s3_client.list_objects_v2(Bucket=bucket_name)

            if 'Contents' not in response:
                return {
                    'statusCode': 200,
                    'body': json.dumps({'guidelines': []})
                }

            guidelines = []
            for obj in response['Contents']:
                if obj['Key'].endswith('.md'):
                    guidelines.append({
                        'file_name': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat()
                    })

            return {
                'statusCode': 200,
                'body': json.dumps({'guidelines': guidelines})
            }

        except Exception as e:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': str(e)})
            }
""")
