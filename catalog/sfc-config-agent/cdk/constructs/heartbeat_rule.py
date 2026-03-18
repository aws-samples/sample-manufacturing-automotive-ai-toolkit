"""
WP-08b — SfcHeartbeatRule CDK Construct.

IoT Topic Rule that listens for heartbeat MQTT messages published by the
edge runner on topic  sfc/{packageId}/heartbeat  and invokes a Lambda
function to persist the heartbeat to the LaunchPackageTable.

Why Lambda instead of the DynamoDB v2 direct action
----------------------------------------------------
The DynamoDB v2 PutItem action fails when the sort-key attribute (``createdAt``)
is an empty string — and the edge runner publishes ``"createdAt": ""`` in
heartbeat payloads because it does not know the value assigned at package-
creation time.  A Lambda action can query the table by ``packageId`` (PK) to
retrieve the real ``createdAt`` SK and then call UpdateItem, which is the
correct operation for updating an existing record rather than creating a
duplicate.

IoT SQL:
  SELECT *, topic(2) AS packageId FROM 'sfc/+/heartbeat'

Lambda handler:  lambda_handlers.heartbeat_ingestion_handler.handler
"""

from __future__ import annotations

import os

from aws_cdk import (
    Duration,
    Stack,
    aws_iam as iam,
    aws_iot as iot,
    aws_lambda as lambda_,
    aws_logs as logs,
)
from constructs import Construct

_HERE = os.path.dirname(__file__)
_HANDLERS_SRC = os.path.join(_HERE, "..", "..", "src")


class SfcHeartbeatRule(Construct):
    """IoT Topic Rule that persists SFC edge heartbeat payloads to DynamoDB."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        launch_package_table,       # aws_dynamodb.ITable
        layer: lambda_.ILayerVersion,  # sfc-cp-utils shared layer
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        region = Stack.of(self).region
        account = Stack.of(self).account
        table_name = launch_package_table.table_name

        # ----------------------------------------------------------------
        # Lambda function — heartbeat ingestion
        # Queries the table by packageId to obtain the real createdAt SK,
        # then calls UpdateItem to set heartbeat attributes.
        # ----------------------------------------------------------------
        self.fn_heartbeat = lambda_.Function(
            self,
            "fn-heartbeat-ingestion",
            function_name="fn-heartbeat-ingestion",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="lambda_handlers.heartbeat_ingestion_handler.handler",
            code=lambda_.Code.from_asset(_HANDLERS_SRC),
            layers=[layer],
            memory_size=128,
            timeout=Duration.seconds(15),
            environment={
                "LAUNCH_PKG_TABLE_NAME": table_name,
            },
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        # Grant the Lambda Query + UpdateItem on the LaunchPackageTable
        launch_package_table.grant_read_write_data(self.fn_heartbeat)

        # ----------------------------------------------------------------
        # IoT Rule — invokes the Lambda
        # ----------------------------------------------------------------
        # IAM role for the IoT Rule Action (Lambda invoke)
        self.rule_role = iam.Role(
            self,
            "HeartbeatRuleRole",
            assumed_by=iam.ServicePrincipal("iot.amazonaws.com"),
            description="Allows IoT heartbeat rule to invoke the heartbeat ingestion Lambda",
        )
        self.rule_role.add_to_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=[self.fn_heartbeat.function_arn],
            )
        )

        # Allow IoT Core to invoke the Lambda (resource-based policy)
        self.fn_heartbeat.add_permission(
            "IoTRuleInvoke",
            principal=iam.ServicePrincipal("iot.amazonaws.com"),
            source_arn=f"arn:aws:iot:{region}:{account}:rule/*",
        )

        self.rule = iot.CfnTopicRule(
            self,
            "SfcHeartbeatRule",
            topic_rule_payload=iot.CfnTopicRule.TopicRulePayloadProperty(
                sql="SELECT *, topic(2) AS packageId FROM 'sfc/+/heartbeat'",
                aws_iot_sql_version="2016-03-23",
                rule_disabled=False,
                actions=[
                    iot.CfnTopicRule.ActionProperty(
                        lambda_=iot.CfnTopicRule.LambdaActionProperty(
                            function_arn=self.fn_heartbeat.function_arn,
                        )
                    )
                ],
                # Error action: republish to a dedicated error topic for debugging
                error_action=iot.CfnTopicRule.ActionProperty(
                    republish=iot.CfnTopicRule.RepublishActionProperty(
                        role_arn=self.rule_role.role_arn,
                        topic="sfc/errors/heartbeat-rule",
                        qos=0,
                    )
                ),
            ),
        )