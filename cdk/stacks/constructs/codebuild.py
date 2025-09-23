"""
CodeBuild Construct for agent deployment projects
"""

from aws_cdk import (
    aws_codebuild as codebuild,
    aws_iam as iam,
    aws_s3 as s3,
    Tags,
    Stack,
    Duration,
)
from constructs import Construct
from typing import Optional, Dict, Any


class CodeBuildConstruct(Construct):
    """
    Manages CodeBuild projects for agent deployment and CDK synthesis.
    """

    def __init__(self, scope: Construct, construct_id: str,
                 agent_role: iam.Role,
                 resource_bucket: s3.Bucket,
                 bedrock_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0",
                 **kwargs) -> None:
        super().__init__(scope, construct_id)
        
        self.agent_role = agent_role
        self.resource_bucket = resource_bucket
        self.bedrock_model_id = bedrock_model_id
        
        # Create CDK synthesis project
        self._create_cdk_synthesis_project()
        
        # Create AgentCore deployment project
        self._create_agentcore_deployment_project()
        
        # Apply tags
        self._apply_tags()

    def _create_cdk_synthesis_project(self) -> None:
        """Create CodeBuild project for CDK synthesis"""
        
        # Define environment variables for CDK synthesis
        environment_variables = {
            'AWS_REGION': codebuild.BuildEnvironmentVariable(
                value=Stack.of(self).region
            ),
            'CDK_DEFAULT_REGION': codebuild.BuildEnvironmentVariable(
                value=Stack.of(self).region
            ),
            'CDK_DEFAULT_ACCOUNT': codebuild.BuildEnvironmentVariable(
                value=Stack.of(self).account
            ),
            'VISTA_FOUNDATION_MODEL': codebuild.BuildEnvironmentVariable(
                value=self.bedrock_model_id
            ),
            'S3_BUCKET_NAME': codebuild.BuildEnvironmentVariable(
                value=self.resource_bucket.bucket_name
            )
        }
        
        # Create the CDK synthesis project
        self.cdk_synthesis_project = codebuild.Project(
            self, "CDKSynthesisProject",
            project_name=f"{Stack.of(self).stack_name}-cdk-synthesis",
            role=self.agent_role,
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.AMAZON_LINUX_2_ARM_3,
                compute_type=codebuild.ComputeType.SMALL,
                environment_variables=environment_variables
            ),
            source=codebuild.Source.s3(
                bucket=self.resource_bucket,
                path="repo"
            ),
            build_spec=codebuild.BuildSpec.from_object(self._get_cdk_synthesis_buildspec()),
            artifacts=codebuild.Artifacts.s3(
                bucket=self.resource_bucket,
                path="cdk-templates",
                include_build_id=False,
                package_zip=False
            ),
            timeout=Duration.minutes(30),
            cache=codebuild.Cache.local(codebuild.LocalCacheMode.DOCKER_LAYER)
        )

    def _create_agentcore_deployment_project(self) -> None:
        """Create CodeBuild project for AgentCore deployment"""
        
        # Define environment variables for AgentCore deployment
        environment_variables = {
            'EXECUTION_ROLE_ARN': codebuild.BuildEnvironmentVariable(
                value=self.agent_role.role_arn
            ),
            'AWS_REGION': codebuild.BuildEnvironmentVariable(
                value=Stack.of(self).region
            ),
            'PYTHONUNBUFFERED': codebuild.BuildEnvironmentVariable(
                value="1"
            )
        }
        
        # Create the AgentCore deployment project
        self.agentcore_deployment_project = codebuild.Project(
            self, "AgentCoreDeploymentProject",
            project_name=f"{Stack.of(self).stack_name}-agent-deployment",
            role=self.agent_role,
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.AMAZON_LINUX_2_ARM_3,
                compute_type=codebuild.ComputeType.SMALL,
                environment_variables=environment_variables
            ),
            source=codebuild.Source.s3(
                bucket=self.resource_bucket,
                path="repo"
            ),
            build_spec=codebuild.BuildSpec.from_object(self._get_agentcore_buildspec()),
            timeout=Duration.minutes(60),
            cache=codebuild.Cache.local(codebuild.LocalCacheMode.DOCKER_LAYER)
        )

    def _get_cdk_synthesis_buildspec(self) -> Dict[str, Any]:
        """Get the build specification for CDK synthesis"""
        return {
            "version": "0.2",
            "phases": {
                "install": {
                    "runtime-versions": {
                        "python": "latest",
                        "nodejs": "latest"
                    },
                    "commands": [
                        "echo 'Installing CDK and dependencies...'",
                        "npm install -g aws-cdk",
                        "pip install --upgrade pip"
                    ]
                },
                "build": {
                    "commands": [
                        "echo 'Synthesizing CDK templates...'",
                        "cd agents_catalog/multi_agent_collaboration/00-vista-agents/cdk",
                        "pip install -r requirements.txt",
                        "cdk synth --output cdk.out",
                        "echo 'CDK synthesis completed'",
                        "ls -la cdk.out/"
                    ]
                }
            },
            "artifacts": {
                "files": [
                    "agents_catalog/multi_agent_collaboration/00-vista-agents/cdk/cdk.out/**/*"
                ]
            },
            "cache": {
                "paths": [
                    "/root/.npm/**/*",
                    "/root/.cache/pip/**/*"
                ]
            }
        }

    def _get_agentcore_buildspec(self) -> Dict[str, Any]:
        """Get the build specification for AgentCore deployment"""
        return {
            "version": "0.2",
            "phases": {
                "install": {
                    "runtime-versions": {
                        "python": "latest"
                    },
                    "commands": [
                        "echo 'Installing dependencies...'",
                        "pip install --upgrade pip",
                        "pip install bedrock-agentcore-starter-toolkit boto3==1.39.9 bedrock-agentcore"
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
                          echo "WARNING: Deployment results file not found"
                        fi
                        """,
                        "echo 'Build completed at $(date)'"
                    ]
                }
            },
            "artifacts": {
                "files": [
                    "agentcore_deployment_results.json",
                    "agents.json",
                    "ui/src/config/agents.json"
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
        }

    def create_dynamic_agentcore_project(self, agent_name: str, agent_config: Dict[str, Any]) -> codebuild.Project:
        """Create a dynamic CodeBuild project for a specific AgentCore agent"""
        
        # Define environment variables for the specific agent
        environment_variables = {
            'EXECUTION_ROLE_ARN': codebuild.BuildEnvironmentVariable(
                value=self.agent_role.role_arn
            ),
            'AWS_REGION': codebuild.BuildEnvironmentVariable(
                value=Stack.of(self).region
            ),
            'AGENT_NAME': codebuild.BuildEnvironmentVariable(
                value=agent_name
            ),
            'PYTHONUNBUFFERED': codebuild.BuildEnvironmentVariable(
                value="1"
            )
        }
        
        # Add any agent-specific environment variables
        for key, value in agent_config.get('environment', {}).items():
            environment_variables[key] = codebuild.BuildEnvironmentVariable(value=str(value))
        
        # Create the agent-specific CodeBuild project
        project = codebuild.Project(
            self, f"AgentProject{self._sanitize_name(agent_name)}",
            project_name=f"{Stack.of(self).stack_name}-{agent_name}-deployment",
            role=self.agent_role,
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.AMAZON_LINUX_2_ARM_3,
                compute_type=codebuild.ComputeType.SMALL,
                environment_variables=environment_variables
            ),
            source=codebuild.Source.s3(
                bucket=self.resource_bucket,
                path="repo"
            ),
            build_spec=codebuild.BuildSpec.from_object(
                self._get_agent_specific_buildspec(agent_name, agent_config)
            ),
            timeout=Duration.minutes(30),
            cache=codebuild.Cache.local(codebuild.LocalCacheMode.DOCKER_LAYER)
        )
        
        # Apply tags
        Tags.of(project).add("Project", "ma3t-agents-toolkit")
        Tags.of(project).add("AgentName", agent_name)
        
        return project

    def _get_agent_specific_buildspec(self, agent_name: str, agent_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get the build specification for a specific AgentCore agent"""
        agent_path = agent_config.get('path', f'agents_catalog/standalone_agents/{agent_name}')
        
        return {
            "version": "0.2",
            "phases": {
                "install": {
                    "runtime-versions": {
                        "python": "latest"
                    },
                    "commands": [
                        "echo 'Installing dependencies for agent: $AGENT_NAME'",
                        "pip install --upgrade pip",
                        "pip install bedrock-agentcore-starter-toolkit boto3 bedrock-agentcore"
                    ]
                },
                "pre_build": {
                    "commands": [
                        "echo 'Starting pre-build phase for agent: $AGENT_NAME'",
                        "aws sts get-caller-identity",
                        f"cd {agent_path}",
                        "ls -la",
                        "if [ -f requirements.txt ]; then pip install -r requirements.txt; fi"
                    ]
                },
                "build": {
                    "commands": [
                        "echo 'Deploying agent: $AGENT_NAME'",
                        "bedrock-agentcore deploy --region $AWS_REGION --execution-role-arn $EXECUTION_ROLE_ARN",
                        "echo 'Agent deployment completed'"
                    ]
                },
                "post_build": {
                    "commands": [
                        "echo 'Post-build phase for agent: $AGENT_NAME'",
                        "echo 'Agent deployment completed successfully'"
                    ]
                }
            },
            "cache": {
                "paths": [
                    "/root/.cache/pip/**/*"
                ]
            }
        }

    def _sanitize_name(self, name: str) -> str:
        """Sanitize agent name for use in CDK construct IDs"""
        return name.replace('-', '').replace('_', '').replace('.', '').replace('/', '')

    def _apply_tags(self) -> None:
        """Apply consistent tags to all CodeBuild projects"""
        Tags.of(self.cdk_synthesis_project).add("Project", "ma3t-agents-toolkit")
        Tags.of(self.cdk_synthesis_project).add("ProjectType", "CDKSynthesis")
        
        Tags.of(self.agentcore_deployment_project).add("Project", "ma3t-agents-toolkit")
        Tags.of(self.agentcore_deployment_project).add("ProjectType", "AgentCoreDeployment")

    @property
    def cdk_synthesis_project_name(self) -> str:
        """Returns the CDK synthesis project name"""
        return self.cdk_synthesis_project.project_name

    @property
    def agentcore_deployment_project_name(self) -> str:
        """Returns the AgentCore deployment project name"""
        return self.agentcore_deployment_project.project_name

    def get_project_by_name(self, project_name: str) -> Optional[codebuild.Project]:
        """Get a CodeBuild project by name"""
        if project_name == self.cdk_synthesis_project.project_name:
            return self.cdk_synthesis_project
        elif project_name == self.agentcore_deployment_project.project_name:
            return self.agentcore_deployment_project
        return None