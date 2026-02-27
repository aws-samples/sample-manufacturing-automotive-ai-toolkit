"""
WP-03 / WP-04–10 / WP-12 — Control Plane API CDK Construct.

Provisions:
  - SfcCpLambdaLayer  (shared sfc_cp_utils layer)
  - fn-configs        (config management — WP-04)
  - fn-launch-pkg     (launch package assembly — WP-06)
  - fn-iot-prov       (IoT provisioning lifecycle — WP-05)
  - fn-logs           (CloudWatch log retrieval — WP-07)
  - fn-gg-comp        (Greengrass v2 component — WP-09)
  - fn-iot-control    (runtime control channel — WP-08)
  - fn-agent-remediate (AI remediation — WP-10)
  - SfcControlPlaneHttpApi (API Gateway HTTP API, OpenAPI import — WP-12)
"""

from __future__ import annotations

import os
import yaml

from aws_cdk import (
    CfnOutput,
    Duration,
    Fn,
    Stack,
    aws_apigatewayv2 as apigwv2,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
)
from constructs import Construct

# Relative path to the layer source (resolved at synth time)
_HERE = os.path.dirname(__file__)
_LAYER_SRC = os.path.join(_HERE, "..", "..", "src", "layer")
_HANDLERS_SRC = os.path.join(_HERE, "..", "..", "src")
_OPENAPI_PATH = os.path.join(_HERE, "..", "openapi", "control-plane-api.yaml")


class ControlPlaneApi(Construct):
    """
    CDK construct that wires the SFC Control Plane Lambda functions and
    API Gateway HTTP API together.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        configs_bucket,          # aws_s3.IBucket — existing SfcConfigBucket
        config_table,            # aws_dynamodb.ITable — SfcConfigTable (existing)
        launch_package_table,    # aws_dynamodb.ITable — LaunchPackageTable (WP-01)
        control_plane_state_table,  # aws_dynamodb.ITable — ControlPlaneStateTable (WP-01)
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        region = Stack.of(self).region
        account = Stack.of(self).account

        # ----------------------------------------------------------------
        # WP-03 — Shared Lambda Layer (sfc_cp_utils)
        # ----------------------------------------------------------------
        self.layer = lambda_.LayerVersion(
            self,
            "SfcCpLayer",
            code=lambda_.Code.from_asset(_LAYER_SRC),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="SFC Control Plane shared utilities (sfc_cp_utils)",
            layer_version_name="sfc-cp-utils",
        )

        # ----------------------------------------------------------------
        # Common Lambda defaults
        # ----------------------------------------------------------------
        common_env = {
            "CONFIGS_BUCKET_NAME": configs_bucket.bucket_name,
            "CONFIG_TABLE_NAME": config_table.table_name,
            "LAUNCH_PKG_TABLE_NAME": launch_package_table.table_name,
            "STATE_TABLE_NAME": control_plane_state_table.table_name,
            "AWS_ACCOUNT_ID": account,
        }

        def _fn(
            fn_id: str,
            handler_file: str,
            handler_fn: str = "handler",
            memory_mb: int = 256,
            timeout_s: int = 30,
            extra_env: dict | None = None,
        ) -> lambda_.Function:
            env = {**common_env, **(extra_env or {})}
            fn = lambda_.Function(
                self,
                fn_id,
                function_name=fn_id.lower().replace("fn", "fn"),
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler=f"lambda_handlers.{handler_file}.{handler_fn}",
                code=lambda_.Code.from_asset(_HANDLERS_SRC),
                layers=[self.layer],
                memory_size=memory_mb,
                timeout=Duration.seconds(timeout_s),
                environment=env,
                log_retention=logs.RetentionDays.ONE_MONTH,
            )
            return fn

        # ----------------------------------------------------------------
        # WP-04 — fn-configs
        # ----------------------------------------------------------------
        self.fn_configs = _fn(
            "fn-configs",
            "config_handler",
            memory_mb=256,
            timeout_s=30,
        )
        configs_bucket.grant_read_write(self.fn_configs)
        config_table.grant_read_write_data(self.fn_configs)
        control_plane_state_table.grant_read_write_data(self.fn_configs)

        # ----------------------------------------------------------------
        # WP-05 — fn-iot-prov
        # ----------------------------------------------------------------
        self.fn_iot_prov = _fn(
            "fn-iot-prov",
            "iot_prov_handler",
            memory_mb=128,
            timeout_s=30,
        )
        launch_package_table.grant_read_write_data(self.fn_iot_prov)
        configs_bucket.grant_read_write(self.fn_iot_prov)
        self._grant_iot_provisioning_permissions(self.fn_iot_prov, region, account)

        # ----------------------------------------------------------------
        # WP-06 — fn-launch-pkg
        # ----------------------------------------------------------------
        self.fn_launch_pkg = _fn(
            "fn-launch-pkg",
            "launch_pkg_handler",
            memory_mb=512,
            timeout_s=60,
        )
        configs_bucket.grant_read_write(self.fn_launch_pkg)
        config_table.grant_read_data(self.fn_launch_pkg)
        launch_package_table.grant_read_write_data(self.fn_launch_pkg)
        control_plane_state_table.grant_read_data(self.fn_launch_pkg)
        self._grant_iot_provisioning_permissions(self.fn_launch_pkg, region, account)

        # ----------------------------------------------------------------
        # WP-07 — fn-logs
        # ----------------------------------------------------------------
        self.fn_logs = _fn(
            "fn-logs",
            "logs_handler",
            memory_mb=256,
            timeout_s=30,
        )
        launch_package_table.grant_read_data(self.fn_logs)
        self.fn_logs.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "logs:FilterLogEvents",
                "logs:GetLogEvents",
                "logs:DescribeLogGroups",
                "logs:DescribeLogStreams",
            ],
            resources=[
                f"arn:aws:logs:{region}:{account}:log-group:/sfc/launch-packages/*",
                f"arn:aws:logs:{region}:{account}:log-group:/sfc/launch-packages/*:*",
            ],
        ))

        # ----------------------------------------------------------------
        # WP-08 — fn-iot-control
        # ----------------------------------------------------------------
        self.fn_iot_control = _fn(
            "fn-iot-control",
            "iot_control_handler",
            memory_mb=128,
            timeout_s=15,
        )
        launch_package_table.grant_read_write_data(self.fn_iot_control)
        configs_bucket.grant_read(self.fn_iot_control)
        self.fn_iot_control.add_to_role_policy(iam.PolicyStatement(
            actions=["iot:Publish"],
            resources=[f"arn:aws:iot:{region}:{account}:topic/sfc/*/control/*"],
        ))

        # ----------------------------------------------------------------
        # WP-09 — fn-gg-comp
        # ----------------------------------------------------------------
        self.fn_gg_comp = _fn(
            "fn-gg-comp",
            "gg_comp_handler",
            memory_mb=256,
            timeout_s=30,
        )
        configs_bucket.grant_read(self.fn_gg_comp)
        launch_package_table.grant_read_write_data(self.fn_gg_comp)
        self.fn_gg_comp.add_to_role_policy(iam.PolicyStatement(
            actions=["greengrassv2:CreateComponentVersion"],
            resources=["*"],
        ))

        # ----------------------------------------------------------------
        # WP-10 — fn-agent-remediate
        # ----------------------------------------------------------------
        self.fn_agent_remediate = _fn(
            "fn-agent-remediate",
            "agent_remediate_handler",
            memory_mb=256,
            timeout_s=120,
        )
        configs_bucket.grant_read_write(self.fn_agent_remediate)
        config_table.grant_read_write_data(self.fn_agent_remediate)
        launch_package_table.grant_read_data(self.fn_agent_remediate)
        # AgentCore invoke_agent_runtime permission
        self.fn_agent_remediate.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock-agentcore:InvokeAgentRuntime"],
            resources=["*"],
        ))
        # Allow SSM read to resolve agentcore-runtime-id at cold-start
        self.fn_agent_remediate.add_to_role_policy(iam.PolicyStatement(
            actions=["ssm:GetParameter"],
            resources=[
                f"arn:aws:ssm:{region}:{account}:parameter/sfc-config-agent/agentcore-runtime-id",
            ],
        ))
        self.fn_agent_remediate.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "logs:FilterLogEvents",
                "logs:GetLogEvents",
                "logs:DescribeLogGroups",
            ],
            resources=[
                f"arn:aws:logs:{region}:{account}:log-group:/sfc/launch-packages/*",
                f"arn:aws:logs:{region}:{account}:log-group:/sfc/launch-packages/*:*",
            ],
        ))

        # ----------------------------------------------------------------
        # WP-12 — API Gateway HTTP API (OpenAPI import)
        # Inject Lambda ARNs into the spec via Fn.sub before import.
        # ----------------------------------------------------------------
        api_log_group = logs.LogGroup(
            self,
            "ApiAccessLogs",
            retention=logs.RetentionDays.ONE_MONTH,
        )

        # Build substitution map for all ARN placeholders in the spec
        substitutions = {
            "FnConfigsArn": _lambda_integration_uri(self.fn_configs),
            "FnLaunchPkgArn": _lambda_integration_uri(self.fn_launch_pkg),
            "FnIotProvArn": _lambda_integration_uri(self.fn_iot_prov),
            "FnLogsArn": _lambda_integration_uri(self.fn_logs),
            "FnGgCompArn": _lambda_integration_uri(self.fn_gg_comp),
            "FnIotControlArn": _lambda_integration_uri(self.fn_iot_control),
            "FnAgentRemediateArn": _lambda_integration_uri(self.fn_agent_remediate),
            # CloudFront origin placeholder — filled at deploy time via stack output
            "CloudFrontOrigin": "https://placeholder.cloudfront.net",
        }

        # Parse the OpenAPI YAML spec to a dict, then recursively replace
        # ${Placeholder} strings with the actual CDK token values.
        # CfnApi.body must be a JSON object (dict), not a string — passing
        # Fn.sub(...) as a string token causes CloudFormation to reject the
        # template with "expected type: JSONObject, found: String".
        with open(_OPENAPI_PATH, "r") as fh:
            spec_dict = yaml.safe_load(fh.read())

        substituted_body = _substitute_in_spec(spec_dict, substitutions)

        self.http_api = apigwv2.CfnApi(
            self,
            "SfcControlPlaneHttpApi",
            body=substituted_body,
            fail_on_warnings=True,
        )

        # Default stage with auto-deploy and access logging
        apigwv2.CfnStage(
            self,
            "DefaultStage",
            api_id=self.http_api.ref,
            stage_name="$default",
            auto_deploy=True,
            access_log_settings=apigwv2.CfnStage.AccessLogSettingsProperty(
                destination_arn=api_log_group.log_group_arn,
                format='{"requestId":"$context.requestId","ip":"$context.identity.sourceIp","requestTime":"$context.requestTime","httpMethod":"$context.httpMethod","routeKey":"$context.routeKey","status":"$context.status","protocol":"$context.protocol","responseLength":"$context.responseLength","integrationError":"$context.integrationErrorMessage"}',
            ),
            default_route_settings=apigwv2.CfnStage.RouteSettingsProperty(
                throttling_burst_limit=100,
                throttling_rate_limit=50,
            ),
        )

        # Grant API Gateway permission to invoke all Lambda functions
        for fn in [
            self.fn_configs,
            self.fn_launch_pkg,
            self.fn_iot_prov,
            self.fn_logs,
            self.fn_gg_comp,
            self.fn_iot_control,
            self.fn_agent_remediate,
        ]:
            fn.add_permission(
                f"ApiGwInvoke-{fn.node.id}",
                principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
                source_arn=f"arn:aws:execute-api:{region}:{account}:{self.http_api.ref}/*",
            )

        # ----------------------------------------------------------------
        # Outputs
        # ----------------------------------------------------------------
        CfnOutput(
            self,
            "SfcControlPlaneApiUrl",
            value=Fn.sub(
                "https://${ApiId}.execute-api.${Region}.amazonaws.com/",
                {"ApiId": self.http_api.ref, "Region": region},
            ),
            description="SFC Control Plane API Gateway invoke URL",
        )

    # ────────────────────────────────────────────────────────────────────
    # Private helpers
    # ────────────────────────────────────────────────────────────────────

    def _grant_iot_provisioning_permissions(
        self, fn: lambda_.Function, region: str, account: str
    ) -> None:
        """Grant IoT + IAM permissions required for thing/cert/role creation."""
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "iot:CreateThing",
                "iot:DeleteThing",
                "iot:CreateKeysAndCertificate",
                "iot:AttachPolicy",
                "iot:DetachPolicy",
                "iot:AttachThingPrincipal",
                "iot:DetachThingPrincipal",
                "iot:CreatePolicy",
                "iot:DeletePolicy",
                "iot:UpdateCertificate",
                "iot:DeleteCertificate",
                "iot:CreateRoleAlias",
                "iot:DeleteRoleAlias",
                "iot:DescribeRoleAlias",
                "iot:DescribeEndpoint",
            ],
            resources=["*"],
        ))
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "iam:CreateRole",
                "iam:GetRole",
                "iam:DeleteRole",
                "iam:PutRolePolicy",
                "iam:DeleteRolePolicy",
                "iam:AttachRolePolicy",
                "iam:DetachRolePolicy",
                "iam:ListAttachedRolePolicies",
                "iam:ListRolePolicies",
                "iam:GetPolicy",
                "iam:PassRole",
                "iam:TagRole",
            ],
            resources=["*"],
        ))
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "logs:CreateLogGroup",
            ],
            resources=[
                f"arn:aws:logs:{region}:{account}:log-group:/sfc/launch-packages/*",
            ],
        ))
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["sts:GetCallerIdentity"],
            resources=["*"],
        ))


def _lambda_integration_uri(fn: lambda_.Function) -> str:
    """
    Build the Lambda proxy integration URI for API Gateway.
    Format: arn:aws:apigateway:{region}:lambda:path/2015-03-31/functions/{fnArn}/invocations
    """
    return Fn.sub(
        "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${FnArn}/invocations",
        {"FnArn": fn.function_arn},
    )


def _substitute_in_spec(obj, substitutions: dict):
    """
    Recursively walk a parsed YAML/JSON structure and replace every occurrence
    of ``${Key}`` in string values with the corresponding CDK token from
    *substitutions*.  This produces a plain Python dict that can be passed
    directly to ``CfnApi(body=...)``, satisfying CloudFormation's requirement
    that the body is a JSON object rather than a string token.
    """
    import re

    if isinstance(obj, dict):
        return {k: _substitute_in_spec(v, substitutions) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute_in_spec(item, substitutions) for item in obj]
    if isinstance(obj, str):
        # If the entire string is a single placeholder, replace it directly
        # so the CDK token type is preserved (important for ARN tokens).
        match = re.fullmatch(r"\$\{(\w+)\}", obj)
        if match and match.group(1) in substitutions:
            return substitutions[match.group(1)]
        # Otherwise do an inline text substitution for embedded placeholders.
        def _replace(m):
            key = m.group(1)
            return substitutions.get(key, m.group(0))
        return re.sub(r"\$\{(\w+)\}", _replace, obj)
    return obj
