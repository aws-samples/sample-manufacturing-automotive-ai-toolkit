"""
AgentCore construct for deploying Bedrock AgentCore agents
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

import aws_cdk as cdk
from aws_cdk import (
    aws_codebuild as codebuild,
    aws_iam as iam,
    aws_s3 as s3,
    aws_s3_assets as s3_assets,
    CustomResource,
    Duration,
)
from constructs import Construct


class AgentCoreConstruct(Construct):
    """
    Construct for deploying Bedrock AgentCore agents.
    
    This construct scans the agents_catalog directory for agents with type 'agentcore'
    and deploys them using the bedrock_agentcore_starter_toolkit.
    """

    def __init__(self, scope: Construct, construct_id: str,
                 agent_role: iam.Role,
                 resource_bucket: s3.Bucket,
                 **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.agent_role = agent_role
        self.resource_bucket = resource_bucket
        self.agentcore_agents = []
        
        # Discover agentcore agents
        self._discover_agentcore_agents()
        
        if self.agentcore_agents:
            # Create CodeBuild project for agentcore deployment
            self._create_agentcore_deployment_project()
        else:
            print("No AgentCore agents found to deploy")

    def _discover_agentcore_agents(self) -> None:
        """Discover agentcore agents from the agents_catalog directory"""
        agents_catalog_path = Path("agents_catalog")
        
        if not agents_catalog_path.exists():
            print("agents_catalog directory not found")
            return
        
        # Walk through the agents_catalog directory
        for manifest_path in agents_catalog_path.rglob("manifest.json"):
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                
                # Check if any agent in the manifest is of type 'agentcore'
                for agent in manifest.get("agents", []):
                    if agent.get("type") == "agentcore":
                        agent_dir = manifest_path.parent
                        agent_id = agent.get("id")
                        agent_name = agent.get("name")
                        entrypoint = agent.get("entrypoint", "agent.py")
                        
                        # Check if the entrypoint file exists
                        entrypoint_path = agent_dir / entrypoint
                        if not entrypoint_path.exists():
                            # Look for other potential entrypoints
                            python_files = list(agent_dir.glob("*.py"))
                            if python_files:
                                entrypoint = python_files[0].name
                                print(f"Entrypoint {agent.get('entrypoint', 'agent.py')} not found in {agent_dir}, using {entrypoint} instead")
                        
                        self.agentcore_agents.append({
                            "path": str(agent_dir),
                            "id": agent_id,
                            "name": agent_name,
                            "entrypoint": entrypoint,
                            "manifest": agent
                        })
                        
                        print(f"Found AgentCore agent: {agent_name} at {agent_dir}")
                        
            except Exception as e:
                print(f"Error processing manifest at {manifest_path}: {e}")

    def _create_agentcore_deployment_project(self) -> None:
        """Create CodeBuild project for deploying AgentCore agents"""
        
        # Create asset for the entire project (including scripts and agents_catalog)
        project_asset = s3_assets.Asset(
            self, "ProjectAsset",
            path=".",
            exclude=[
                "cdk/cdk.out/**",
                "cdk/__pycache__/**",
                ".git/**",
                ".venv/**",
                "ui/node_modules/**",
                "ui/.next/**",
                "*.pyc",
                "__pycache__/**"
            ]
        )
        
        # Create CodeBuild project
        self.agentcore_deployment_project = codebuild.Project(
            self, "AgentCoreDeploymentProject",
            project_name=f"{cdk.Stack.of(self).stack_name}-agentcore-deployment",
            role=self.agent_role,
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.AMAZON_LINUX_2_ARM_3,
                compute_type=codebuild.ComputeType.SMALL,
                environment_variables={
                    "AWS_REGION": codebuild.BuildEnvironmentVariable(
                        value=cdk.Stack.of(self).region
                    ),
                    "EXECUTION_ROLE_ARN": codebuild.BuildEnvironmentVariable(
                        value=self.agent_role.role_arn
                    ),
                    "S3_BUCKET_NAME": codebuild.BuildEnvironmentVariable(
                        value=self.resource_bucket.bucket_name
                    )
                }
            ),
            source=codebuild.Source.s3(
                bucket=project_asset.bucket,
                path=project_asset.s3_object_key
            ),
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "phases": {
                    "install": {
                        "runtime-versions": {
                            "python": "latest"
                        },
                        "commands": [
                            "echo 'Installing dependencies...'",
                            "pip install --upgrade pip",
                            "pip install bedrock-agentcore-starter-toolkit boto3==1.39.9 bedrock-agentcore",
                            "pip install -r scripts/requirements.txt"
                        ]
                    },
                    "pre_build": {
                        "commands": [
                            "echo 'Starting pre-build phase at $(date)'",
                            "echo 'Checking AWS credentials and configuration...'",
                            "aws sts get-caller-identity",
                            "echo $AWS_REGION",
                            "echo $EXECUTION_ROLE_ARN"
                        ]
                    },
                    "build": {
                        "commands": [
                            "echo 'Starting build phase at $(date)'",
                            "echo 'Deploying AgentCore agents...'",
                            "python scripts/build_launch_agentcore.py --region $AWS_REGION --execution-role-arn $EXECUTION_ROLE_ARN",
                            "echo 'AgentCore deployment completed'"
                        ]
                    },
                    "post_build": {
                        "commands": [
                            "echo 'Starting post-build phase at $(date)'",
                            "echo 'Checking deployment results...'",
                            "cat agentcore_deployment_results.json || echo 'No results file found'",
                            """
                            if [ -f agentcore_deployment_results.json ]; then
                              FAILED_AGENTS=$(cat agentcore_deployment_results.json | grep -c "error" || echo "0")
                              if [ $FAILED_AGENTS -gt 0 ]; then
                                echo "WARNING: $FAILED_AGENTS agents failed to deploy"
                                cat agentcore_deployment_results.json | grep -A 2 "error" || echo "No error details found"
                              else
                                echo "All agents deployed successfully"
                              fi
                            else
                              echo "ERROR: Deployment results file not found"
                              exit 1
                            fi
                            """,
                            "echo 'Build completed at $(date)'"
                        ]
                    }
                },
                "artifacts": {
                    "files": [
                        "agentcore_deployment_results.json",
                        "agents.json"
                    ],
                    "discard-paths": False
                },
                "cache": {
                    "paths": [
                        "/root/.cache/pip/**/*"
                    ]
                },
                "env": {
                    "variables": {
                        "PYTHONUNBUFFERED": "1"
                    }
                }
            }),
            artifacts=codebuild.Artifacts.s3(
                bucket=self.resource_bucket,
                path="agentcore-deployment-results",
                include_build_id=True
            ),
            timeout=Duration.minutes(30)
        )
        
        # Grant necessary permissions to the CodeBuild project
        self.resource_bucket.grant_read_write(self.agentcore_deployment_project)
        project_asset.bucket.grant_read(self.agentcore_deployment_project)
        
        # Add ECR permissions for container management
        self.agentcore_deployment_project.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:GetAuthorizationToken",
                    "ecr:CreateRepository",
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                    "ecr:InitiateLayerUpload",
                    "ecr:UploadLayerPart",
                    "ecr:CompleteLayerUpload",
                    "ecr:PutImage",
                    "ecr:TagResource",
                    "ecr:DescribeRepositories"
                ],
                resources=["*"]
            )
        )
        
        # Add Bedrock AgentCore permissions
        self.agentcore_deployment_project.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:CreateAgent",
                    "bedrock-agentcore:UpdateAgent",
                    "bedrock-agentcore:GetAgent",
                    "bedrock-agentcore:ListAgents",
                    "bedrock-agentcore:DeleteAgent",
                    "bedrock-agentcore:InvokeAgent"
                ],
                resources=[f"arn:aws:bedrock-agentcore:{cdk.Stack.of(self).region}:{cdk.Stack.of(self).account}:agent/*"]
            )
        )

    def get_agentcore_agents(self) -> List[Dict[str, Any]]:
        """Get list of discovered agentcore agents"""
        return self.agentcore_agents

    def get_deployment_project(self) -> Optional[codebuild.Project]:
        """Get the CodeBuild deployment project"""
        return getattr(self, 'agentcore_deployment_project', None)

    def trigger_deployment(self) -> None:
        """Trigger the agentcore deployment (for manual execution)"""
        if hasattr(self, 'agentcore_deployment_project'):
            # This would typically be called externally or via a custom resource
            print(f"AgentCore deployment project created: {self.agentcore_deployment_project.project_name}")
            print("To deploy AgentCore agents, run the CodeBuild project manually or via CLI")
        else:
            print("No AgentCore deployment project available")