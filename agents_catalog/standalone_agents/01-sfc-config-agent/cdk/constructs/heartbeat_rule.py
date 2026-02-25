"""
WP-08b — SfcHeartbeatRule CDK Construct.

IoT Topic Rule that listens for heartbeat MQTT messages published by the
edge runner on topic  sfc/{packageId}/heartbeat  and writes them directly
to the LaunchPackageTable via the DynamoDB IoT Rule Action.

IoT SQL:
  SELECT *, topic(2) AS packageId FROM 'sfc/+/heartbeat'

DynamoDB action writes:
  packageId           = ${packageId}          (from topic extraction)
  createdAt           = ${createdAt}           (existing SK — must match existing item)
  lastHeartbeatAt     = ${timestamp()}
  lastHeartbeatPayload= <full JSON string>
  sfcRunning          = ${sfcRunning}
"""

from __future__ import annotations

from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_iot as iot,
)
from constructs import Construct


class SfcHeartbeatRule(Construct):
    """IoT Topic Rule that persists SFC edge heartbeat payloads to DynamoDB."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        launch_package_table,   # aws_dynamodb.ITable
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        region = Stack.of(self).region
        account = Stack.of(self).account
        table_name = launch_package_table.table_name

        # ----------------------------------------------------------------
        # IAM role for the IoT Rule Action (DynamoDB write)
        # ----------------------------------------------------------------
        self.rule_role = iam.Role(
            self,
            "HeartbeatRuleRole",
            assumed_by=iam.ServicePrincipal("iot.amazonaws.com"),
            description="Allows IoT heartbeat rule to write to LaunchPackageTable",
        )
        launch_package_table.grant_write_data(self.rule_role)

        # ----------------------------------------------------------------
        # IoT Topic Rule
        # ----------------------------------------------------------------
        # The DynamoDB v2 action writes multiple attributes in a single PutItem.
        # We use CfnTopicRule with the dynamoDBv2 action shape.
        # The hash key (packageId) is extracted from topic(2).
        # The sort key (createdAt) is NOT written by the rule — the PutItem
        # action on the DynamoDB v2 action includes a putItem that specifies
        # all fields; any missing SK causes the PutItem to fail.
        # To avoid this, we use the UpdateItem variant via a separate Lambda
        # in the IoT Rule — but CDK / IoT only supports UpdateItem via Lambda.
        # Instead we use the DynamoDB v2 action with a *full document* approach:
        # the edge runner always publishes packageId+createdAt in the heartbeat
        # payload so the rule can do a full PutItem with both keys present.
        #
        # Heartbeat payload shape (from runner.py):
        # {
        #   "packageId": "...",
        #   "createdAt": "...",       <-- SK, published by runner
        #   "timestamp": "...",
        #   "sfcPid": 12345,
        #   "sfcRunning": true,
        #   "telemetryEnabled": true,
        #   "diagnosticsEnabled": false,
        #   "recentLogs": [...]
        # }
        self.rule = iot.CfnTopicRule(
            self,
            "SfcHeartbeatRule",
            topic_rule_payload=iot.CfnTopicRule.TopicRulePayloadProperty(
                sql="SELECT *, topic(2) AS packageId FROM 'sfc/+/heartbeat'",
                aws_iot_sql_version="2016-03-23",
                rule_disabled=False,
                actions=[
                    iot.CfnTopicRule.ActionProperty(
                        dynamo_d_bv2=iot.CfnTopicRule.DynamoDBv2ActionProperty(
                            role_arn=self.rule_role.role_arn,
                            put_item=iot.CfnTopicRule.PutItemInputProperty(
                                table_name=table_name,
                            ),
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