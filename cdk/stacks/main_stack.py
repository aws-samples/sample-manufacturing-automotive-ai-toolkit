"""
Manufacturing & Automotive AI Toolkit (MA3T) Main Stack
"""

import aws_cdk as cdk
from aws_cdk import (
    CfnParameter,
    CfnOutput,
    CfnCondition,
    Fn,
)
from constructs import Construct
from typing import Dict, Any, List, Optional

# Import our constructs
from .constructs.agentcore import AgentCoreConstruct
from .constructs.storage import StorageConstruct
from .constructs.iam import IAMConstruct
from .constructs.compute import ComputeConstruct
from .constructs.codebuild import CodeBuildConstruct
from .nested_stack_registry import AgentRegistry, CDKStackConfig, AgentCoreConfig


class MainStack(cdk.Stack):
    """
    Manages all core infrastructure and orchestrates nested stacks.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create CDK parameters matching CloudFormation template
        self._create_parameters()

        # Create conditions
        self._create_conditions()

        # Create shared infrastructure in proper order
        self._create_shared_infrastructure()

        # Auto-discover and deploy agents
        self._setup_agent_registry()

        # Create stack outputs
        self._create_outputs()

        # Apply CDK-Nag suppressions for demo/development environment
        self._apply_stack_suppressions()

        # Upload local code to S3
        self._upload_local_code()

        # Trigger agent deployments after stack creation
        self._create_deployment_trigger()

    def _create_shared_infrastructure(self) -> None:
        """Create shared infrastructure constructs in proper order"""

        # 1. Create Storage construct (S3 bucket and DynamoDB tables)
        bucket_name = None
        if self.s3_bucket_name_param.value_as_string:
            bucket_name = self.s3_bucket_name_param.value_as_string

        self.storage_construct = StorageConstruct(
            self, "Storage",
            s3_bucket_name=bucket_name
        )

        # 2. Create IAM construct (roles and policies)
        self.iam_construct = IAMConstruct(
            self, "IAM",
            resource_bucket=self.storage_construct.resource_bucket
        )

        # 3. Create Compute construct (Lambda functions)
        self.compute_construct = ComputeConstruct(
            self, "Compute",
            tables=self.storage_construct.tables,
            lambda_role=self.iam_construct.lambda_execution_role,
            resource_bucket=self.storage_construct.resource_bucket
        )

        # 4. Create CodeBuild construct (deployment projects)
        self.codebuild_construct = CodeBuildConstruct(
            self, "CodeBuild",
            agent_role=self.iam_construct.bedrock_agent_role,
            resource_bucket=self.storage_construct.resource_bucket,
            apprunner_access_role=self.iam_construct.apprunner_access_role,
            apprunner_instance_role=self.iam_construct.apprunner_instance_role,
            bedrock_model_id=self.bedrock_model_param.value_as_string
        )

        # Store references for easy access
        self.resource_bucket = self.storage_construct.resource_bucket
        self.agent_role = self.iam_construct.bedrock_agent_role
        self.lambda_execution_role = self.iam_construct.lambda_execution_role
        self.tables = self.storage_construct.tables
        self.lambda_functions = self.compute_construct.get_all_functions()
        self.codebuild_projects = {
            'agentcore_deployment': self.codebuild_construct.agentcore_deployment_project
        }

    def _setup_agent_registry(self) -> None:
        """Set up agent registry and auto-discover agents"""

        # Create agent registry
        self.agent_registry = AgentRegistry(self)

        # Discover agents
        cdk_stacks, agentcore_agents = self.agent_registry.discover_agents()

        # Get shared resources for nested stacks
        shared_resources = self.get_shared_resources()

        # Register CDK nested stacks
        self.nested_stacks = []
        for cdk_config in cdk_stacks:
            nested_stack = self.agent_registry.register_cdk_stack(
                cdk_config, shared_resources)
            if nested_stack:
                self.nested_stacks.append(nested_stack)

        # AgentCore agents will be discovered and deployed by build_launch_agentcore.py
        # running in the CodeBuild project - no need to create individual projects here
        self.agentcore_projects = []
        print(
            f"Discovered {len(agentcore_agents)} AgentCore agents - will be deployed by CodeBuild")

    def _create_parameters(self) -> None:
        """Create CDK parameters matching the CloudFormation template"""

        self.bedrock_model_param = CfnParameter(
            self, "BedrockModelId",
            type="String",
            default="anthropic.claude-3-haiku-20240307-v1:0",
            description="The Bedrock model ID to use for the agents"
        )

        self.deploy_application_param = CfnParameter(
            self, "DeployApplication",
            type="String",
            default="false",
            allowed_values=["true", "false"],
            description="Whether to deploy the application"
        )

        self.use_local_code_param = CfnParameter(
            self, "UseLocalCode",
            type="String",
            default="false",
            allowed_values=["true", "false"],
            description="Whether to use local code instead of GitHub. Set to true when using deploy.sh script."
        )

        self.github_url_param = CfnParameter(
            self, "GitHubUrl",
            type="String",
            default="https://github.com/aws-samples/manufacturing-automotive-ai-toolkit.git",
            description="URL of the GitHub repository to download (only used if UseLocalCode is false)"
        )

        self.git_branch_param = CfnParameter(
            self, "GitBranch",
            type="String",
            default="main",
            description="Branch name to download (only used if UseLocalCode is false)"
        )

        self.s3_bucket_name_param = CfnParameter(
            self, "S3BucketName",
            type="String",
            default="",
            description="Name of the S3 bucket to use for code storage"
        )

    def _create_conditions(self) -> None:
        """Create conditions matching the CloudFormation template"""

        self.use_github_code_condition = CfnCondition(
            self, "UseGitHubCode",
            expression=Fn.condition_equals(
                self.use_local_code_param.value_as_string, "false")
        )

        self.create_s3_bucket_condition = CfnCondition(
            self, "CreateS3Bucket",
            expression=Fn.condition_equals(
                self.s3_bucket_name_param.value_as_string, "")
        )

    def _create_outputs(self) -> None:
        """Create stack outputs matching the CloudFormation template"""

        # Core infrastructure outputs
        CfnOutput(
            self, "AgentRole",
            value=self.agent_role.role_arn,
            description="Amazon Bedrock Service Role ARN"
        )

        CfnOutput(
            self, "S3BucketNameOutput",
            value=self.resource_bucket.bucket_name,
            description="S3 bucket name used for code storage"
        )

        CfnOutput(
            self, "ResourceBucketName",
            value=self.resource_bucket.bucket_name,
            description="Resource bucket name for deploy script"
        )



        CfnOutput(
            self, "AgentCoreDeploymentProject",
            value=self.codebuild_construct.agentcore_deployment_project.project_name,
            description="CodeBuild project for deploying AgentCore agents"
        )

        CfnOutput(
            self, "AppRunnerAccessRoleArn",
            value=self.iam_construct.apprunner_access_role_arn,
            description="App Runner ECR access role ARN"
        )

        CfnOutput(
            self, "AppRunnerInstanceRoleArn",
            value=self.iam_construct.apprunner_instance_role_arn,
            description="App Runner instance role ARN"
        )

        # Additional outputs for discovered agents
        if hasattr(self, 'nested_stacks') and self.nested_stacks:
            CfnOutput(
                self, "NestedStacksCount",
                value=str(len(self.nested_stacks)),
                description="Number of CDK nested stacks deployed"
            )

        if hasattr(self, 'agentcore_projects') and self.agentcore_projects:
            CfnOutput(
                self, "AgentCoreProjectsCount",
                value=str(len(self.agentcore_projects)),
                description="Number of AgentCore CodeBuild projects created"
            )

        # Table names output
        if self.tables:
            table_names = list(self.tables.keys())
            CfnOutput(
                self, "DynamoDBTables",
                value=",".join(table_names),
                description="Names of created DynamoDB tables"
            )

        # Lambda function names output
        if self.lambda_functions:
            function_names = list(self.lambda_functions.keys())
            CfnOutput(
                self, "LambdaFunctions",
                value=",".join(function_names),
                description="Names of created Lambda functions"
            )

    def _create_deployment_trigger(self) -> None:
        """Create a custom resource to trigger agent deployments after stack creation"""
        from aws_cdk import aws_lambda as lambda_
        from aws_cdk import custom_resources as cr
        from aws_cdk import CustomResource

        # Create a Lambda function to trigger CodeBuild
        trigger_function = lambda_.Function(
            self, "DeploymentTriggerFunction",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=lambda_.Code.from_inline("""
import boto3
import json

def handler(event, context):
    print(f"Event: {json.dumps(event)}")

    if event['RequestType'] == 'Create' or event['RequestType'] == 'Update':
        codebuild = boto3.client('codebuild')

        # Get the project name from the event
        project_name = event['ResourceProperties'].get('ProjectName')

        if project_name:
            try:
                response = codebuild.start_build(projectName=project_name)
                build_id = response['build']['id']
                print(f"Started CodeBuild project {project_name} with build ID: {build_id}")

                return {
                    'PhysicalResourceId': f"deployment-trigger-{build_id}",
                    'Data': {
                        'BuildId': build_id,
                        'ProjectName': project_name
                    }
                }
            except Exception as e:
                print(f"Error starting CodeBuild: {str(e)}")
                # Don't fail the stack deployment if CodeBuild fails
                return {
                    'PhysicalResourceId': 'deployment-trigger-failed',
                    'Data': {
                        'Error': str(e)
                    }
                }

    return {
        'PhysicalResourceId': event.get('PhysicalResourceId', 'deployment-trigger'),
        'Data': {}
    }
"""),
            timeout=cdk.Duration.minutes(5)
        )

        # Grant permissions to start CodeBuild projects
        trigger_function.add_to_role_policy(
            cdk.aws_iam.PolicyStatement(
                actions=["codebuild:StartBuild"],
                resources=[
                    f"arn:aws:codebuild:{self.region}:{self.account}:project/*"]
            )
        )

        # Create custom resource provider
        provider = cr.Provider(
            self, "DeploymentTriggerProvider",
            on_event_handler=trigger_function
        )

        # Create custom resource to trigger AgentCore deployment
        CustomResource(
            self, "TriggerAgentCoreDeployment",
            service_token=provider.service_token,
            properties={
                'ProjectName': self.codebuild_construct.agentcore_deployment_project.project_name
            }
        )

    def _upload_local_code(self) -> None:
        """
        Upload local code to S3 for CodeBuild projects

        Note: Code upload is handled manually after CDK deployment
        using the deploy_cdk.sh script, just like the CloudFormation version.
        This avoids CDK asset bundling issues.
        """
        pass

    def get_shared_resources(self) -> Dict[str, Any]:
        """
        Return shared resources that can be used by nested stacks and agents.
        """
        return {
            # Parameters
            'bedrock_model_id': self.bedrock_model_param.value_as_string,
            'deploy_application': self.deploy_application_param.value_as_string,
            'use_local_code': self.use_local_code_param.value_as_string,
            'github_url': self.github_url_param.value_as_string,
            'git_branch': self.git_branch_param.value_as_string,
            's3_bucket_name': self.s3_bucket_name_param.value_as_string,

            # Stack information
            'stack_name': self.stack_name,
            'region': self.region,
            'account': self.account,

            # Storage resources
            'resource_bucket': self.resource_bucket,
            'resource_bucket_name': self.resource_bucket.bucket_name if self.resource_bucket else None,
            'resource_bucket_arn': self.resource_bucket.bucket_arn if self.resource_bucket else None,
            'tables': self.tables,

            # IAM resources
            'agent_role': self.agent_role,
            'agent_role_arn': self.agent_role.role_arn if self.agent_role else None,
            'lambda_execution_role': self.lambda_execution_role,
            'lambda_execution_role_arn': self.lambda_execution_role.role_arn if self.lambda_execution_role else None,
            'codebuild_service_role': getattr(self.iam_construct, 'codebuild_service_role', None),

            # Compute resources
            'lambda_functions': self.lambda_functions,
            'business_functions': getattr(self.compute_construct, 'business_functions', {}),
            'data_functions': getattr(self.compute_construct, 'data_functions', {}),

            # CodeBuild resources
            'codebuild_projects': self.codebuild_projects,
            'agentcore_deployment_project': self.codebuild_construct.agentcore_deployment_project,

            # Constructs (for advanced usage)
            'storage_construct': self.storage_construct,
            'iam_construct': self.iam_construct,
            'compute_construct': self.compute_construct,
            'codebuild_construct': self.codebuild_construct
        }

    def get_agent_summary(self) -> Dict[str, Any]:
        """Get a summary of all discovered and deployed agents"""
        summary = {
            'cdk_nested_stacks': [],
            'agentcore_agents': [],
            'total_agents': 0
        }

        if hasattr(self, 'agent_registry'):
            discovered = self.agent_registry.list_discovered_agents()
            summary['cdk_nested_stacks'] = discovered.get('cdk_stacks', [])
            summary['agentcore_agents'] = discovered.get(
                'agentcore_agents', [])
            summary['total_agents'] = len(
                summary['cdk_nested_stacks']) + len(summary['agentcore_agents'])

        return summary

    def get_resource_summary(self) -> Dict[str, Any]:
        """Get a summary of all created resources"""
        return {
            'storage': {
                'bucket_name': self.resource_bucket.bucket_name if self.resource_bucket else None,
                'tables_count': len(self.tables),
                'table_names': list(self.tables.keys())
            },
            'compute': {
                'lambda_functions_count': len(self.lambda_functions),
                'function_names': list(self.lambda_functions.keys())
            },
            'codebuild': {
                'projects_count': len(self.codebuild_projects),
                'project_names': list(self.codebuild_projects.keys())
            },
            'agents': self.get_agent_summary()
        }

    def _apply_stack_suppressions(self) -> None:
        """Apply CDK-Nag suppressions at stack level for demo/development environment"""
        from cdk_nag import NagSuppressions

        # Suppress IAM wildcard permissions across the entire stack
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Wildcard permissions acceptable for demo/development toolkit requiring dynamic AWS service access"
                },
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "AWS managed policies acceptable for demo/development environment"
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Lambda runtime versions managed by CDK defaults, acceptable for demo environment"
                },
                {
                    "id": "AwsSolutions-CB4",
                    "reason": "CodeBuild encryption with AWS managed keys sufficient for demo environment"
                },
                {
                    "id": "AwsSolutions-DDB3",
                    "reason": "DynamoDB point-in-time recovery not required for demo data"
                }
            ]
        )
