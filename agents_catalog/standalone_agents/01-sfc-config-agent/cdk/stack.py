#!/usr/bin/env python3
"""
CDK Stack for SFC Config Agent Infrastructure
Creates S3 bucket, DynamoDB table, and AgentCore Memory store
for the SFC Config Generation Agent.
"""

from aws_cdk import (
    NestedStack,
    Stack,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_s3 as s3,
    aws_ssm as ssm,
    CustomResource,
    Duration,
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
    - IAM execution role for AgentCore Memory
    - AgentCore Memory store (via SDK-backed custom resource)
    - SSM parameters for all resource identifiers
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
        # AgentCore Memory execution role
        # Trusted by the bedrock-agentcore service for memory consolidation.
        # Requires Bedrock model invocation so the service can embed/summarise
        # conversation turns into the memory store.
        # Ref: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-create-a-memory-store.html
        # ----------------------------------------------------------------
        self.memory_execution_role = iam.Role(
            self, "SfcAgentMemoryExecutionRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description="Execution role for SFC Config Agent AgentCore Memory consolidation",
        )

        # Allow the memory service to invoke Bedrock foundation models
        # (used for semantic embedding and summary consolidation)
        self.memory_execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=[
                    f"arn:aws:bedrock:{Stack.of(self).region}::foundation-model/*"
                ],
            )
        )

        # Allow writing consolidation logs
        self.memory_execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}"
                    ":log-group:/aws/bedrock-agentcore/*"
                ],
            )
        )

        # ----------------------------------------------------------------
        # AgentCore Memory store — Python Lambda-backed custom resource
        #
        # AWS::BedrockAgentCore::Memory is not yet a native CloudFormation
        # resource type. We use a Python Lambda + boto3 so we are not
        # dependent on a specific JS SDK npm package name.
        #
        # The Lambda handles Create (returns memoryId as PhysicalResourceId)
        # and Delete (calls delete_memory with the stored memoryId).
        # ----------------------------------------------------------------
        memory_handler_code = (
            "import json, boto3, urllib.request\n"
            "\n"
            "SUCCESS = 'SUCCESS'\n"
            "FAILED  = 'FAILED'\n"
            "\n"
            "def send(event, context, status, data, physical_id, reason=''):\n"
            "    body = json.dumps({\n"
            "        'Status': status, 'Reason': reason,\n"
            "        'PhysicalResourceId': physical_id,\n"
            "        'StackId': event['StackId'],\n"
            "        'RequestId': event['RequestId'],\n"
            "        'LogicalResourceId': event['LogicalResourceId'],\n"
            "        'Data': data,\n"
            "    }).encode()\n"
            "    req = urllib.request.Request(event['ResponseURL'],\n"
            "        data=body, method='PUT',\n"
            "        headers={'Content-Type': '', 'Content-Length': len(body)})\n"
            "    urllib.request.urlopen(req)\n"
            "\n"
            "def handler(event, context):\n"
            "    props  = event.get('ResourceProperties', {})\n"
            "    region = props.get('Region')\n"
            "    req_type = event['RequestType']\n"
            "    physical_id = event.get('PhysicalResourceId', 'pending')\n"
            "    try:\n"
            "        client = boto3.client('bedrock-agentcore-control',\n"
            "                              region_name=region)\n"
            "        if req_type == 'Create':\n"
            "            resp = client.create_memory(\n"
            "                name=props['MemoryName'],\n"
            "                description=props['Description'],\n"
            "                memoryExecutionRoleArn=props['MemoryExecutionRoleArn'],\n"
            "                eventExpiryDuration=int(props.get('EventExpiryDuration', 90)),\n"
            "                memoryStrategies=[{\n"
            "                    'semanticMemoryStrategy': {\n"
            "                        'name': 'sfc_semantic_memory',\n"
            "                        'description': (\n"
            "                            'Captures key SFC topology facts and '\n"
            "                            'protocol preferences from conversations.'),\n"
            "                    }\n"
            "                }],\n"
            "            )\n"
            "            mem = resp.get('memory', resp)\n"
            "            # API may return 'id' or 'memoryId' depending on SDK version\n"
            "            memory_id = (mem.get('memoryId') or mem.get('id')\n"
            "                         or resp.get('memoryId'))\n"
            "            if not memory_id:\n"
            "                raise KeyError('memoryId not found in response: ' + str(resp))\n"
            "            send(event, context, SUCCESS,\n"
            "                 {'MemoryId': memory_id}, memory_id)\n"
            "        elif req_type == 'Delete':\n"
            "            if physical_id and physical_id != 'pending':\n"
            "                try:\n"
            "                    client.delete_memory(memoryId=physical_id)\n"
            "                except client.exceptions.ResourceNotFoundException:\n"
            "                    pass  # already gone — not an error\n"
            "            send(event, context, SUCCESS, {}, physical_id)\n"
            "        else:  # Update — no-op\n"
            "            send(event, context, SUCCESS, {}, physical_id)\n"
            "    except Exception as exc:\n"
            "        send(event, context, FAILED, {}, physical_id, str(exc))\n"
        )

        memory_handler_fn = lambda_.Function(
            self, "SfcMemoryHandlerFn",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_inline(memory_handler_code),
            timeout=Duration.minutes(5),
            description="Custom resource handler: create/delete AgentCore Memory for SFC agent",
        )

        # Grant the Lambda permission to call AgentCore Memory control-plane APIs
        memory_handler_fn.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:CreateMemory",
                    "bedrock-agentcore:DeleteMemory",
                    "bedrock-agentcore:GetMemory",
                ],
                resources=["*"],
            )
        )

        # Grant the Lambda permission to pass the memory execution role to AgentCore
        memory_handler_fn.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["iam:PassRole"],
                resources=[self.memory_execution_role.role_arn],
            )
        )

        # The Lambda handles cfn-response signalling itself (calls send()),
        # so use the function ARN directly as the service token rather than
        # wrapping it with cr.Provider (which would conflict).
        self.memory_resource = CustomResource(
            self, "SfcAgentCoreMemory",
            service_token=memory_handler_fn.function_arn,
            properties={
                "Region": Stack.of(self).region,
                "MemoryName": "sfc_config_agent_memory",
                "Description": (
                    "Persistent memory store for the SFC Config Generation Agent. "
                    "Retains semantic context across sessions to improve configuration "
                    "quality and reduce repeated context-setting."
                ),
                "MemoryExecutionRoleArn": self.memory_execution_role.role_arn,
                # Retention period (days) for raw conversation events before
                # they are consolidated into the semantic memory store.
                "EventExpiryDuration": "90",
            },
        )

        # Ensure the execution role exists before the Lambda tries to pass it
        self.memory_resource.node.add_dependency(self.memory_execution_role)

        # ----------------------------------------------------------------
        # Grant the shared agent role (container runtime) permission to
        # read/write sessions and events in the AgentCore Memory store.
        # These actions are used by AgentCoreMemorySessionManager in agent.py.
        # Also grant SSM read so the container can resolve /sfc-config-agent/memory-id
        # at startup (agent.py reads MEM_ID from SSM if env var is absent).
        # ----------------------------------------------------------------
        if shared_resources and shared_resources.get("agent_role"):
            agent_role: iam.IRole = shared_resources["agent_role"]
            agent_role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "bedrock-agentcore:GetMemory",
                        "bedrock-agentcore:CreateEvent",
                        "bedrock-agentcore:ListEvents",
                        "bedrock-agentcore:GetSession",
                        "bedrock-agentcore:CreateSession",
                        "bedrock-agentcore:UpdateSession",
                        "bedrock-agentcore:ListSessions",
                        "bedrock-agentcore:DeleteSession",
                    ],
                    # Scope to this account/region; the memory ARN is not yet
                    # resolvable at synth time so we use a wildcard here.
                    resources=[
                        f"arn:aws:bedrock-agentcore:{Stack.of(self).region}"
                        f":{Stack.of(self).account}:memory/*"
                    ],
                )
            )
            # Allow the container to read the memory ID from SSM at startup
            agent_role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["ssm:GetParameter"],
                    resources=[
                        f"arn:aws:ssm:{Stack.of(self).region}:{Stack.of(self).account}"
                        ":parameter/sfc-config-agent/memory-id"
                    ],
                )
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

        NagSuppressions.add_resource_suppressions(
            self.memory_execution_role,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": (
                        "Wildcard on foundation-model/* required: the specific model used "
                        "for memory consolidation is resolved at runtime by the AgentCore "
                        "service, not at synth time."
                    ),
                },
            ],
            apply_to_children=True,
        )

        # ----------------------------------------------------------------
        # SSM Parameters — allow the agent container to discover all
        # resources at runtime without hard-coding ARNs or IDs.
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

        # The memory ID is read by agent.py via the AGENTCORE_MEMORY_ID env-var,
        # which the AgentCore deployment tooling (build_launch_agentcore.py) injects
        # into the container environment by reading this SSM parameter.
        # get_att_string("MemoryId") maps to the Data.MemoryId key returned by
        # the Lambda handler in its cfn-response Data payload.
        ssm.StringParameter(
            self, "SfcMemoryIdParameter",
            parameter_name="/sfc-config-agent/memory-id",
            string_value=self.memory_resource.get_att_string("MemoryId"),
            description="AgentCore Memory store ID for SFC Config Agent",
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
        CfnOutput(
            self, "SfcMemoryId",
            value=self.memory_resource.get_att_string("MemoryId"),
            description="AgentCore Memory store ID for SFC Config Agent",
        )
        CfnOutput(
            self, "SfcMemoryExecutionRoleArn",
            value=self.memory_execution_role.role_arn,
            description="IAM role ARN used by AgentCore Memory for consolidation",
        )