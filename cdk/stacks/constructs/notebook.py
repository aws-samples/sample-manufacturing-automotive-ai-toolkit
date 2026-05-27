"""
SageMaker Notebook Construct for AgentCore development environments
"""

import base64
from aws_cdk import (
    aws_sagemaker as sagemaker,
    aws_iam as iam,
    CfnOutput,
)
from constructs import Construct


class NotebookConstruct(Construct):
    """Creates a SageMaker notebook instance pre-configured for AgentCore development."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        notebook_name: str,
        instance_type: str = "ml.t3.medium",
        volume_size_gb: int = 20,
        shared_resources: dict = None,
        **kwargs
    ):
        super().__init__(scope, construct_id, **kwargs)

        shared_resources = shared_resources or {}
        
        # Create notebook execution role
        self.notebook_role = iam.Role(
            self, "NotebookRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSageMakerFullAccess"),
            ],
        )

        # Add Bedrock permissions for AgentCore
        self.notebook_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock-agentcore:*",
                ],
                resources=["*"],
            )
        )

        # Grant access to shared S3 bucket if available
        if shared_resources.get("resource_bucket"):
            shared_resources["resource_bucket"].grant_read_write(self.notebook_role)

        # Lifecycle config to install AgentCore dependencies
        on_create_script = self._create_lifecycle_script()
        
        self.lifecycle_config = sagemaker.CfnNotebookInstanceLifecycleConfig(
            self, "LifecycleConfig",
            notebook_instance_lifecycle_config_name=f"{notebook_name}-lifecycle",
            on_create=[
                sagemaker.CfnNotebookInstanceLifecycleConfig.NotebookInstanceLifecycleHookProperty(
                    content=base64.b64encode(on_create_script.encode()).decode()
                )
            ],
        )

        # Create notebook instance
        self.notebook = sagemaker.CfnNotebookInstance(
            self, "Notebook",
            instance_type=instance_type,
            role_arn=self.notebook_role.role_arn,
            notebook_instance_name=notebook_name,
            volume_size_in_gb=volume_size_gb,
            lifecycle_config_name=self.lifecycle_config.notebook_instance_lifecycle_config_name,
        )
        self.notebook.add_dependency(self.lifecycle_config)

        from cdk_nag import NagSuppressions
        NagSuppressions.add_resource_suppressions(
            self.notebook,
            [
                {"id": "AwsSolutions-SM1", "reason": "VPC not required for notebook development environment"},
                {"id": "AwsSolutions-SM2", "reason": "KMS encryption not required for development notebooks"},
                {"id": "AwsSolutions-SM3", "reason": "Direct internet access needed for pip installs"},
            ],
        )

        CfnOutput(self, "NotebookName", value=self.notebook.notebook_instance_name)

    def _create_lifecycle_script(self) -> str:
        """Generate lifecycle script for AgentCore setup."""
        return """#!/bin/bash
set -e

# Install AgentCore and Strands dependencies
sudo -u ec2-user -i <<'EOF'
source /home/ec2-user/anaconda3/bin/activate python3
pip install --upgrade pip
pip install strands-agents strands-agents-tools bedrock-agentcore boto3
conda deactivate
EOF
"""
