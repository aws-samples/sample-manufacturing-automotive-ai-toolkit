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
                 apprunner_access_role: iam.Role,
                 apprunner_instance_role: iam.Role,
                 bedrock_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0",
                 **kwargs) -> None:
        super().__init__(scope, construct_id)

        self.agent_role = agent_role
        self.resource_bucket = resource_bucket
        self.apprunner_access_role = apprunner_access_role
        self.apprunner_instance_role = apprunner_instance_role
        self.bedrock_model_id = bedrock_model_id

        # Create AgentCore deployment project
        self._create_agentcore_deployment_project()

        # Apply tags
        self._apply_tags()

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
            'S3_BUCKET': codebuild.BuildEnvironmentVariable(
                value=self.resource_bucket.bucket_name
            ),
            'PYTHONUNBUFFERED': codebuild.BuildEnvironmentVariable(
                value="1"
            ),
            'APPRUNNER_ACCESS_ROLE_ARN': codebuild.BuildEnvironmentVariable(
                value=self.apprunner_access_role.role_arn
            ),
            'APPRUNNER_INSTANCE_ROLE_ARN': codebuild.BuildEnvironmentVariable(
                value=self.apprunner_instance_role.role_arn
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
                environment_variables=environment_variables,
                privileged=True
            ),
            source=codebuild.Source.s3(
                bucket=self.resource_bucket,
                path=""  # Root of bucket where repo zip file is located
            ),
            build_spec=codebuild.BuildSpec.from_object(
                self._get_agentcore_buildspec()),
            timeout=Duration.minutes(60),
            cache=codebuild.Cache.local(codebuild.LocalCacheMode.DOCKER_LAYER)
        )

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
                        "echo 'Current working directory:'",
                        "pwd",
                        "echo 'Listing ALL files in current directory:'",
                        "ls -la",
                        "echo 'Looking for repo file:'",
                        "find . -name 'repo*' -type f || echo 'No repo files found'",
                        "echo 'Checking if repo file exists:'",
                        "if [ -f repo ]; then echo 'repo file exists'; else echo 'repo file does not exist'; fi",
                        "echo 'Trying to extract project files...'",
                        "if [ -f repo ]; then unzip -q repo -d . && echo 'Extraction successful'; else echo 'Cannot extract - repo file missing'; fi",
                        "echo 'Listing directory contents after extraction:'",
                        "ls -la",
                        "echo 'Checking for agents_catalog directory:'",
                        "ls -la agents_catalog/ || echo 'agents_catalog directory not found'",
                        "echo 'Checking for manifest files:'",
                        "find . -name 'manifest.json' -type f || echo 'No manifest.json files found'",
                        "echo 'Checking AWS credentials and configuration...'",
                        "aws sts get-caller-identity",
                        "echo $AWS_REGION",
                        "echo $EXECUTION_ROLE_ARN"
                    ]
                },
                "build": {
                    "commands": [
                        "echo 'Starting build phase at $(date)'",
                        "echo 'Listing and managing AgentCore agents...'",
                        "python scripts/build_launch_agentcore.py --region $AWS_REGION --execution-role-arn $EXECUTION_ROLE_ARN",
                        "echo 'AgentCore management completed'",
                        "",
                        "echo 'Starting UI build...'",
                        "cd ui",
                        "echo 'Installing UI dependencies...'",
                        "npm ci",
                        "echo 'Running UI build...'",
                        "npm run build",
                        "echo 'UI build completed'",
                        "",
                        "echo 'Building and deploying Docker container...'",
                        "echo 'Logging into ECR or creating new repo'",
                        "ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)",
                        "aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com",
                        "aws ecr describe-repositories --repository-names ma3t-ui --region $AWS_REGION || aws ecr create-repository --repository-name ma3t-ui --region $AWS_REGION",
                        "",
                        "echo 'Building docker image'",
                        "ECR_URI=$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/ma3t-ui",
                        "docker build -f Dockerfile -t ma3t-ui .",
                        "docker tag ma3t-ui:latest $ECR_URI:latest",
                        "docker push $ECR_URI:latest",
                        "",
                        "echo 'Deploy to App Runner'",
                        "SERVICE_NAME=ma3t-ui-service",
                        "ACCESS_ROLE_ARN=$APPRUNNER_ACCESS_ROLE_ARN",
                        "INSTANCE_ROLE_ARN=$APPRUNNER_INSTANCE_ROLE_ARN",
                        "",
                        "SERVICE_ARN=$(aws apprunner list-services --query \"ServiceSummaryList[?ServiceName=='$SERVICE_NAME'].ServiceArn\" --output text --region $AWS_REGION)",
                        "echo \"Found service ARN: $SERVICE_ARN\"",
                        "if [ -n \"$SERVICE_ARN\" ] && [ \"$SERVICE_ARN\" != \"None\" ]; then echo 'Updating existing App Runner service...'; aws apprunner update-service --service-arn $SERVICE_ARN --source-configuration '{\"ImageRepository\":{\"ImageIdentifier\":\"'$ECR_URI':latest\",\"ImageConfiguration\":{\"Port\":\"3000\"},\"ImageRepositoryType\":\"ECR\"},\"AutoDeploymentsEnabled\":false,\"AuthenticationConfiguration\":{\"AccessRoleArn\":\"'$ACCESS_ROLE_ARN'\"}}' --region $AWS_REGION; aws apprunner update-service --service-arn $SERVICE_ARN --instance-configuration '{\"InstanceRoleArn\":\"'$INSTANCE_ROLE_ARN'\"}' --region $AWS_REGION; else echo 'Creating new App Runner service...'; aws apprunner create-service --service-name $SERVICE_NAME --source-configuration '{\"ImageRepository\":{\"ImageIdentifier\":\"'$ECR_URI':latest\",\"ImageConfiguration\":{\"Port\":\"3000\"},\"ImageRepositoryType\":\"ECR\"},\"AutoDeploymentsEnabled\":false,\"AuthenticationConfiguration\":{\"AccessRoleArn\":\"'$ACCESS_ROLE_ARN'\"}}' --region $AWS_REGION; SERVICE_ARN=$(aws apprunner list-services --query \"ServiceSummaryList[?ServiceName=='$SERVICE_NAME'].ServiceArn\" --output text --region $AWS_REGION); aws apprunner update-service --service-arn $SERVICE_ARN --instance-configuration '{\"InstanceRoleArn\":\"'$INSTANCE_ROLE_ARN'\"}' --region $AWS_REGION; fi",
                        "",
                        
                    ]
                },
                "post_build": {
                    "commands": [
                        "echo 'Starting post-build phase at $(date)'",
                        "echo 'Checking deployment results...'",
                        "cat agentcore_deployment_results.json || echo 'No results file found'",
                        "if [ -f agentcore_deployment_results.json ]; then FAILED_AGENTS=$(cat agentcore_deployment_results.json | grep -c \"error\" || echo \"0\"); if [ $FAILED_AGENTS -gt 0 ]; then echo \"WARNING: $FAILED_AGENTS agents failed to deploy\"; cat agentcore_deployment_results.json | grep -A 2 \"error\" || echo \"No error details found\"; else echo \"All agents deployed successfully\"; fi; else echo \"WARNING: Deployment results file not found\"; fi",
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
            environment_variables[key] = codebuild.BuildEnvironmentVariable(
                value=str(value))

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
        agent_path = agent_config.get(
            'path', f'agents_catalog/standalone_agents/{agent_name}')

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
        Tags.of(self.agentcore_deployment_project).add(
            "Project", "ma3t-agents-toolkit")
        Tags.of(self.agentcore_deployment_project).add(
            "ProjectType", "AgentCoreDeployment")

    @property
    def agentcore_deployment_project_name(self) -> str:
        """Returns the AgentCore deployment project name"""
        return self.agentcore_deployment_project.project_name

    def get_project_by_name(self, project_name: str) -> Optional[codebuild.Project]:
        """Get a CodeBuild project by name"""
        if project_name == self.agentcore_deployment_project.project_name:
            return self.agentcore_deployment_project
        return None
