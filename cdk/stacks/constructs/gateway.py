"""
MCP Gateway construct for deploying MCP servers to AgentCore Gateway.

This is an L3-style construct that wraps L1 CfnGateway/CfnGatewayTarget resources
with auto-discovery of MCP servers, Lambda creation, and IAM grants.
"""

import json
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

import jsii
import aws_cdk as cdk
from aws_cdk import (
    aws_bedrockagentcore as agentcore,
    aws_lambda as lambda_,
    aws_iam as iam,
    Duration,
    Tags,
    Stack,
)
from constructs import Construct


@jsii.implements(cdk.ILocalBundling)
class _PipLocalBundling:
    """Bundles a Python Lambda by running pip install locally (no Docker)."""

    def __init__(self, source_path: str) -> None:
        self._source_path = source_path

    def try_bundle(self, output_dir: str, options: Any = None, **kwargs) -> bool:
        try:
            req_file = os.path.join(self._source_path, "requirements.txt")
            if os.path.exists(req_file):
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install",
                     "-r", req_file, "-t", output_dir, "--quiet"],
                )
            for item in os.listdir(self._source_path):
                src = os.path.join(self._source_path, item)
                dst = os.path.join(output_dir, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
            return True
        except Exception as exc:
            print(f"Local bundling failed ({exc}), falling back to Docker")
            return False


class McpGatewayConstruct(Construct):
    """
    Discovers MCP servers from a configurable directory and deploys them
    as Lambda-backed targets on an AgentCore Gateway.

    Each subdirectory must contain:
      - mcp_config.json  (server name, Lambda config, tool definitions)
      - lambda_function.py (or whatever handler the config specifies)
      - requirements.txt   (pip dependencies)
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        gateway_role: iam.Role,
        mcp_servers_path: Optional[str] = None,
        authorizer_type: str = "AWS_IAM",
        authorizer_discovery_url: Optional[str] = None,
        authorizer_allowed_clients: Optional[List[str]] = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.gateway_role = gateway_role
        self.mcp_servers: List[Dict[str, Any]] = []
        self.lambda_functions: Dict[str, lambda_.Function] = {}
        self._mcp_servers_path = mcp_servers_path
        self._authorizer_type = authorizer_type
        self._authorizer_discovery_url = authorizer_discovery_url
        self._authorizer_allowed_clients = authorizer_allowed_clients or []

        self._discover_mcp_servers()

        if not self.mcp_servers:
            print("No MCP servers found")
            return

        self._create_gateway()

        for server in self.mcp_servers:
            self._create_server_resources(server)

        Tags.of(self).add("Component", "McpGateway")

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def _discover_mcp_servers(self) -> None:
        """Scan mcp-servers/ directory for server configs."""
        if self._mcp_servers_path:
            mcp_servers_path = self._mcp_servers_path
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            workspace_root = os.path.dirname(
                os.path.dirname(os.path.dirname(current_dir))
            )
            mcp_servers_path = os.path.join(workspace_root, "mcp-servers")

        if not os.path.exists(mcp_servers_path):
            return

        for entry in sorted(os.listdir(mcp_servers_path)):
            server_dir = os.path.join(mcp_servers_path, entry)
            config_path = os.path.join(server_dir, "mcp_config.json")

            if not os.path.isdir(server_dir) or not os.path.exists(config_path):
                continue

            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                config["_dir_name"] = entry
                config["_path"] = server_dir
                self.mcp_servers.append(config)
                print(f"Found MCP server: {config.get('name', entry)}")
            except Exception as e:
                print(f"Error reading MCP config in {entry}: {e}")

    # ------------------------------------------------------------------
    # Gateway
    # ------------------------------------------------------------------

    def _create_gateway(self) -> None:
        """Create the AgentCore MCP Gateway."""
        stack_name = Stack.of(self).stack_name

        gateway_props = dict(
            name=f"{stack_name}-mcp-gateway",
            role_arn=self.gateway_role.role_arn,
            protocol_type="MCP",
            authorizer_type=self._authorizer_type,
            protocol_configuration=agentcore.CfnGateway.GatewayProtocolConfigurationProperty(
                mcp=agentcore.CfnGateway.MCPGatewayConfigurationProperty(
                    supported_versions=["2025-03-26"],
                ),
            ),
        )

        if self._authorizer_type == "CUSTOM_JWT" and self._authorizer_discovery_url:
            gateway_props["authorizer_configuration"] = agentcore.CfnGateway.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=agentcore.CfnGateway.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=self._authorizer_discovery_url,
                    allowed_clients=self._authorizer_allowed_clients,
                ),
            )

        self.gateway = agentcore.CfnGateway(self, "McpGateway", **gateway_props)

    @property
    def gateway_url(self) -> str:
        """The Gateway URL for MCP connections."""
        return self.gateway.attr_gateway_url

    # ------------------------------------------------------------------
    # Per-server resources (Lambda + GatewayTarget)
    # ------------------------------------------------------------------

    def _create_server_resources(self, server: Dict[str, Any]) -> None:
        server_name = server["name"]
        server_path = server["_path"]
        dir_name = server["_dir_name"]
        lambda_cfg = server.get("lambda", {})
        sanitized = self._sanitize_name(dir_name)

        runtime = self._get_runtime(lambda_cfg.get("runtime", "python3.11"))

        fn = lambda_.Function(
            self,
            f"Fn{sanitized}",
            function_name=f"{Stack.of(self).stack_name}-mcp-{server_name}",
            runtime=runtime,
            handler=lambda_cfg.get("handler", "lambda_function.lambda_handler"),
            code=lambda_.Code.from_asset(
                server_path,
                bundling=cdk.BundlingOptions(
                    local=_PipLocalBundling(server_path),
                    image=runtime.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output"
                        " && cp -a . /asset-output",
                    ],
                ),
            ),
            timeout=Duration.seconds(lambda_cfg.get("timeout", 30)),
            memory_size=lambda_cfg.get("memorySize", 512),
            environment=lambda_cfg.get("environment", {}),
        )

        self.lambda_functions[server_name] = fn

        # Let the Gateway role invoke the Lambda
        fn.grant_invoke(self.gateway_role)

        # Build tool definitions from config
        tool_defs = self._build_tool_definitions(server.get("tools", []))

        agentcore.CfnGatewayTarget(
            self,
            f"Target{sanitized}",
            gateway_identifier=self.gateway.ref,
            name=server_name,
            credential_provider_configurations=[
                agentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE",
                ),
            ],
            target_configuration=agentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=agentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    lambda_=agentcore.CfnGatewayTarget.McpLambdaTargetConfigurationProperty(
                        lambda_arn=fn.function_arn,
                        tool_schema=agentcore.CfnGatewayTarget.ToolSchemaProperty(
                            inline_payload=tool_defs,
                        ),
                    ),
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Tool schema helpers
    # ------------------------------------------------------------------

    def _build_tool_definitions(self, tools: List[Dict[str, Any]]) -> list:
        """Convert tool configs from mcp_config.json into CDK property objects."""
        return [
            agentcore.CfnGatewayTarget.ToolDefinitionProperty(
                name=t["name"],
                description=t["description"],
                input_schema=self._convert_schema(t["inputSchema"]),
            )
            for t in tools
        ]

    def _convert_schema(self, schema: Dict[str, Any]):
        """Recursively convert a JSON schema dict to a SchemaDefinitionProperty."""
        props: Dict[str, Any] = {}

        if "type" in schema:
            props["type"] = schema["type"]
        if "description" in schema:
            props["description"] = schema["description"]
        if "required" in schema:
            props["required"] = schema["required"]
        if "properties" in schema:
            props["properties"] = {
                k: self._convert_schema(v)
                for k, v in schema["properties"].items()
            }
        if "items" in schema:
            props["items"] = self._convert_schema(schema["items"])

        return agentcore.CfnGatewayTarget.SchemaDefinitionProperty(**props)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _get_runtime(runtime_str: str) -> lambda_.Runtime:
        return {
            "python3.9": lambda_.Runtime.PYTHON_3_9,
            "python3.11": lambda_.Runtime.PYTHON_3_11,
            "python3.12": lambda_.Runtime.PYTHON_3_12,
            "nodejs18.x": lambda_.Runtime.NODEJS_18_X,
            "nodejs20.x": lambda_.Runtime.NODEJS_20_X,
        }.get(runtime_str, lambda_.Runtime.PYTHON_3_11)

    @staticmethod
    def _sanitize_name(name: str) -> str:
        return "".join(c for c in name if c.isalnum())

    def get_gateway(self) -> Optional[agentcore.CfnGateway]:
        return getattr(self, "gateway", None)

    def get_lambda_functions(self) -> Dict[str, lambda_.Function]:
        return self.lambda_functions
