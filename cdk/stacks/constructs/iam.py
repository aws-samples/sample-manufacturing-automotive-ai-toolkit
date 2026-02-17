"""
IAM Construct for roles and policies
"""

from aws_cdk import (
    aws_iam as iam,
    aws_s3 as s3,
    Tags,
    Stack,
)
from cdk_nag import NagSuppressions
from constructs import Construct
from typing import Optional


class IAMConstruct(Construct):
    """
    Manages all IAM roles and policies for the MA3T application.
    """

    def __init__(self, scope: Construct, construct_id: str,
                 resource_bucket: Optional[s3.Bucket] = None, **kwargs) -> None:
        super().__init__(scope, construct_id)

        self.resource_bucket = resource_bucket

        # Create the main agent role that combines all permissions
        self._create_bedrock_agent_role()

        # Create separate Lambda execution role
        self._create_lambda_execution_role()

        # Create App Runner roles
        self._create_apprunner_roles()

        # Create CodeBuild service role
        self._create_codebuild_service_role()

        # Apply CDK-Nag suppressions after all roles are created
        self._apply_cdk_nag_suppressions()

        # Apply tags
        self._apply_tags()

    def _create_bedrock_agent_role(self) -> None:
        """Create the main Bedrock agent execution role with comprehensive permissions"""

        # Create the role with multiple service principals
        self.bedrock_agent_role = iam.Role(
            self, "AgentRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("bedrock.amazonaws.com"),
                iam.ServicePrincipal("lambda.amazonaws.com"),
                iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
                iam.ServicePrincipal("codebuild.amazonaws.com")
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole")
            ]
        )

        # Add CDK-Nag suppressions for AgentRole
        NagSuppressions.add_resource_suppressions(
            self.bedrock_agent_role,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "AWS managed policies are acceptable for demo/development environments. AWSLambdaBasicExecutionRole is well-maintained and secure.",
                    "appliesTo": ["Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"]
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Wildcard permissions required for Bedrock agents to access models, knowledge bases, and AgentCore operations dynamically in demo environment.",
                    "appliesTo": [
                        "Action::bedrock:*",
                        "Action::bedrock-agentcore:*", 
                        "Action::apprunner:*",
                        "Action::application-signals:*",
                        "Action::cloudwatch:*",
                        "Action::ecr-public:*",
                        "Action::kms:*",
                        "Action::secretsmanager:*",
                        "Action::xray:*",
                        "Resource::*"
                    ]
                }
            ]
        )

        # Add Bedrock permissions
        self._add_bedrock_permissions()

        # Add ECR permissions
        self._add_ecr_permissions()

        # Add Bedrock AgentCore permissions (comprehensive set matching working version)
        self._add_bedrock_agentcore_permissions()

        # Add S3 permissions
        self._add_s3_permissions()

        # Add CloudWatch Logs permissions
        self._add_cloudwatch_logs_permissions()

        # Add SSM permissions
        self._add_ssm_permissions()

        # Add IAM PassRole permissions
        self._add_iam_passrole_permissions()

    def _create_lambda_execution_role(self) -> None:
        """Create a dedicated Lambda execution role"""
        self.lambda_execution_role = iam.Role(
            self, "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole")
            ]
        )

        # Add DynamoDB permissions for Lambda functions
        self.lambda_execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                    "dynamodb:BatchGetItem",
                    "dynamodb:BatchWriteItem"
                ],
                resources=[
                    f"arn:aws:dynamodb:{Stack.of(self).region}:{Stack.of(self).account}:table/*"
                ]
            )
        )

        # Add Bedrock invoke permissions for Lambda functions
        self.lambda_execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                resources=[
                    f"arn:{Stack.of(self).partition}:bedrock:*::foundation-model/*"
                ]
            )
        )

    def _create_codebuild_service_role(self) -> None:
        """Create a dedicated CodeBuild service role"""
        self.codebuild_service_role = iam.Role(
            self, "CodeBuildServiceRole",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "CloudWatchLogsFullAccess")
            ]
        )

        # Add S3 permissions for CodeBuild
        if self.resource_bucket:
            self.codebuild_service_role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "s3:GetObject",
                        "s3:GetObjectVersion",
                        "s3:GetObjectAcl",
                        "s3:PutObject",
                        "s3:ListBucket"
                    ],
                    resources=[
                        self.resource_bucket.bucket_arn,
                        f"{self.resource_bucket.bucket_arn}/*"
                    ]
                )
            )

        # Add ECR permissions for CodeBuild
        self.codebuild_service_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ecr:GetAuthorizationToken"],
                resources=["*"]
            )
        )

        self.codebuild_service_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
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
                resources=[
                    f"arn:aws:ecr:{Stack.of(self).region}:{Stack.of(self).account}:repository/ma3t-*",
                    f"arn:aws:ecr:{Stack.of(self).region}:{Stack.of(self).account}:repository/bedrock-*"
                ]
            )
        )

        # Add S3 permissions for AgentCore CodeBuild sources bucket
        self.codebuild_service_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:GetObject"],
                resources=[
                    f"arn:aws:s3:::bedrock-agentcore-codebuild-sources-{Stack.of(self).account}-{Stack.of(self).region}/*"
                ]
            )
        )

        # Add S3 bucket lifecycle permissions for AgentCore
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:PutLifecycleConfiguration",
                    "s3:GetLifecycleConfiguration",
                    "s3:CreateBucket",
                    "s3:HeadBucket"
                ],
                resources=[
                    f"arn:aws:s3:::bedrock-agentcore-codebuild-sources-{Stack.of(self).account}-{Stack.of(self).region}"
                ]
            )
        )

        # Add Bedrock AgentCore permissions to CodeBuild role (same as main agent role)
        self.codebuild_service_role.add_to_policy(
            iam.PolicyStatement(
                sid="IAMRoleManagement",
                effect=iam.Effect.ALLOW,
                actions=[
                    "iam:CreateRole",
                    "iam:DeleteRole",
                    "iam:GetRole",
                    "iam:PutRolePolicy",
                    "iam:DeleteRolePolicy",
                    "iam:AttachRolePolicy",
                    "iam:DetachRolePolicy",
                    "iam:TagRole",
                    "iam:ListRolePolicies",
                    "iam:ListAttachedRolePolicies"
                ],
                resources=[
                    f"arn:aws:iam::{Stack.of(self).account}:role/*BedrockAgentCore*",
                    f"arn:aws:iam::{Stack.of(self).account}:role/service-role/*BedrockAgentCore*"
                ]
            )
        )

        self.codebuild_service_role.add_to_policy(
            iam.PolicyStatement(
                sid="CodeBuildProjectAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "codebuild:StartBuild",
                    "codebuild:BatchGetBuilds",
                    "codebuild:ListBuildsForProject",
                    "codebuild:CreateProject",
                    "codebuild:UpdateProject",
                    "codebuild:BatchGetProjects"
                ],
                resources=[
                    f"arn:aws:codebuild:{Stack.of(self).region}:{Stack.of(self).account}:project/bedrock-agentcore-*",
                    f"arn:aws:codebuild:{Stack.of(self).region}:{Stack.of(self).account}:build/bedrock-agentcore-*"
                ]
            )
        )

        self.codebuild_service_role.add_to_policy(
            iam.PolicyStatement(
                sid="CodeBuildListAccess",
                effect=iam.Effect.ALLOW,
                actions=["codebuild:ListProjects"],
                resources=["*"]
            )
        )

        self.codebuild_service_role.add_to_policy(
            iam.PolicyStatement(
                sid="IAMPassRoleAccess",
                effect=iam.Effect.ALLOW,
                actions=["iam:PassRole"],
                resources=[
                    f"arn:aws:iam::{Stack.of(self).account}:role/AmazonBedrockAgentCore*",
                    f"arn:aws:iam::{Stack.of(self).account}:role/service-role/AmazonBedrockAgentCore*"
                ]
            )
        )

        # Add the missing bedrock-agentcore permissions to CodeBuild role
        self.codebuild_service_role.add_to_policy(
            iam.PolicyStatement(
                sid="BedrockAgentCoreRuntimeAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:CreateAgentRuntime",
                    "bedrock-agentcore:DeleteAgentRuntime",
                    "bedrock-agentcore:GetAgentRuntime",
                    "bedrock-agentcore:ListAgentRuntimes",
                    "bedrock-agentcore:UpdateAgentRuntime",
                    "bedrock-agentcore:CreateAgent",
                    "bedrock-agentcore:UpdateAgent",
                    "bedrock-agentcore:GetAgent",
                    "bedrock-agentcore:ListAgents",
                    "bedrock-agentcore:DeleteAgent",
                    "bedrock-agentcore:InvokeAgent",
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
                    "bedrock-agentcore:GetAgentRuntimeEndpoint",
                    "bedrock-agentcore:CreateWorkloadIdentity"
                ],
                resources=[
                    f"arn:aws:bedrock-agentcore:{Stack.of(self).region}:{Stack.of(self).account}:*"
                ]
            )
        )

        # Add App Runner permissions
        self.codebuild_service_role.add_to_policy(
            iam.PolicyStatement(
                sid="AppRunnerAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "apprunner:CreateService",
                    "apprunner:UpdateService",
                    "apprunner:DescribeService",
                    "apprunner:ListServices",
                    "apprunner:StartDeployment"
                ],
                resources=["*"]
            )
        )

        # Add IAM PassRole for App Runner roles
        self.codebuild_service_role.add_to_policy(
            iam.PolicyStatement(
                sid="AppRunnerPassRole",
                effect=iam.Effect.ALLOW,
                actions=["iam:PassRole"],
                resources=[
                    self.apprunner_access_role.role_arn,
                    self.apprunner_instance_role.role_arn
                ]
            )
        )

    def _create_apprunner_roles(self) -> None:
        """Create App Runner access and instance roles"""
        
        # App Runner ECR Access Role
        self.apprunner_access_role = iam.Role(
            self, "AppRunnerECRAccessRole",
            assumed_by=iam.ServicePrincipal("build.apprunner.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSAppRunnerServicePolicyForECRAccess"
                )
            ]
        )

        # App Runner Instance Role
        self.apprunner_instance_role = iam.Role(
            self, "AppRunnerInstanceRole", 
            assumed_by=iam.ServicePrincipal("tasks.apprunner.amazonaws.com")
        )

        # Add Bedrock permissions to instance role
        self.apprunner_instance_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:InvokeAgentRuntime",
                    "bedrock:ListAgents",
                    "bedrock:InvokeInlineAgent", 
                    "bedrock:GetAgentAlias",
                    "bedrock:GetAgent",
                    "bedrock:ListAgentAliases",
                    "bedrock:InvokeModel",
                    "bedrock:InvokeAgent",
                    "bedrock:ListAgentVersions"
                ],
                resources=["*"]
            )
        )

        # Add Lambda invoke permissions for agent action groups
        self.apprunner_instance_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[f"arn:aws:lambda:{Stack.of(self).region}:{Stack.of(self).account}:function:*"]
            )
        )

        # Add DynamoDB permissions for agent data access
        self.apprunner_instance_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Query",
                    "dynamodb:Scan"
                ],
                resources=[f"arn:aws:dynamodb:{Stack.of(self).region}:{Stack.of(self).account}:table/*"]
            )
        )

    def _add_bedrock_permissions(self) -> None:
        """Add Bedrock-specific permissions to the agent role"""
        # Comprehensive Bedrock permissions are handled in _add_bedrock_agentcore_permissions
        pass

    def _add_ecr_permissions(self) -> None:
        """Add ECR permissions to the agent role"""
        # Comprehensive ECR permissions are handled in _add_bedrock_agentcore_permissions
        pass

    def _add_bedrock_agentcore_permissions(self) -> None:
        """Add comprehensive permissions matching the working cdk-test version"""
        
        # Basic CodeBuild permissions
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream", 
                    "logs:PutLogEvents",
                    "logs:PutResourcePolicy"
                ],
                resources=["*"]
            )
        )
        
        # S3 permissions
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:GetObjectVersion",
                    "s3:GetObjectAcl",
                    "s3:PutObject",
                    "s3:PutObjectAcl",
                    "s3:GetBucketAcl",
                    "s3:GetBucketLocation",
                    "s3:ListBucket",
                    "s3:CreateBucket",
                    "s3:PutBucketPolicy"
                ],
                resources=["*"]
            )
        )
        
        # ECR permissions
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                    "ecr:CreateRepository",
                    "ecr:InitiateLayerUpload",
                    "ecr:UploadLayerPart",
                    "ecr:CompleteLayerUpload",
                    "ecr:PutImage",
                    "ecr:TagResource",
                    "ecr:DescribeRepositories",
                    "ecr-public:*"
                ],
                resources=["*"]
            )
        )
        
        # Bedrock permissions
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:*",
                    "bedrock-agentcore:*"
                ],
                resources=["*"]
            )
        )
        
        # IAM permissions for AgentCore
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "iam:GetRole",
                    "iam:CreateRole",
                    "iam:AttachRolePolicy",
                    "iam:PutRolePolicy",
                    "iam:TagRole",
                    "iam:PassRole",
                    "iam:GetRolePolicy",
                    "iam:ListAttachedRolePolicies",
                    "iam:ListRolePolicies",
                    "iam:ListRoles",
                    "iam:CreateServiceLinkedRole"
                ],
                resources=["*"]
            )
        )
        
        # CodeBuild permissions
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "codebuild:CreateProject",
                    "codebuild:UpdateProject",
                    "codebuild:StartBuild",
                    "codebuild:BatchGetBuilds"
                ],
                resources=["*"]
            )
        )
        
        # Additional services
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "sts:GetServiceBearerToken",
                    "secretsmanager:*",
                    "kms:*",
                    "lambda:ListFunctions",
                    "application-signals:*",
                    "cloudwatch:*",
                    "xray:*",
                    "apprunner:*"
                ],
                resources=["*"]
            )
        )

    def _add_s3_permissions(self) -> None:
        """Add S3 permissions to the agent role"""
        # Comprehensive S3 permissions are handled in _add_bedrock_agentcore_permissions
        pass

    def _add_cloudwatch_logs_permissions(self) -> None:
        """Add CloudWatch Logs permissions to the agent role"""
        # Comprehensive CloudWatch permissions are handled in _add_bedrock_agentcore_permissions
        pass

    def _add_ssm_permissions(self) -> None:
        """Add SSM permissions to the agent role"""
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:GetParameter",
                    "ssm:PutParameter",
                    "ssm:StartSession"
                ],
                resources=[
                    f"arn:aws:ssm:{Stack.of(self).region}:{Stack.of(self).account}:parameter/*",
                    f"arn:aws:codebuild:{Stack.of(self).region}:{Stack.of(self).account}:build/*"
                ]
            )
        )

    def _add_iam_passrole_permissions(self) -> None:
        """Add IAM PassRole permissions to the agent role"""
        # Comprehensive IAM permissions are handled in _add_bedrock_agentcore_permissions
        pass

        pass

    def _apply_tags(self) -> None:
        """Apply consistent tags to all IAM resources"""
        Tags.of(self.bedrock_agent_role).add("Project", "ma3t-agents-toolkit")
        Tags.of(self.lambda_execution_role).add(
            "Project", "ma3t-agents-toolkit")
        Tags.of(self.codebuild_service_role).add(
            "Project", "ma3t-agents-toolkit")
        Tags.of(self.apprunner_access_role).add(
            "Project", "ma3t-agents-toolkit")
        Tags.of(self.apprunner_instance_role).add(
            "Project", "ma3t-agents-toolkit")

    @property
    def agent_role_arn(self) -> str:
        """Returns the Bedrock agent role ARN"""
        return self.bedrock_agent_role.role_arn

    @property
    def lambda_role_arn(self) -> str:
        """Returns the Lambda execution role ARN"""
        return self.lambda_execution_role.role_arn

    @property
    def codebuild_role_arn(self) -> str:
        """Returns the CodeBuild service role ARN"""
        return self.codebuild_service_role.role_arn

    @property
    def apprunner_access_role_arn(self) -> str:
        """Returns the App Runner ECR access role ARN"""
        return self.apprunner_access_role.role_arn

    @property
    def apprunner_instance_role_arn(self) -> str:
        """Returns the App Runner instance role ARN"""
        return self.apprunner_instance_role.role_arn

    def _apply_cdk_nag_suppressions(self) -> None:
        """Apply CDK-Nag suppressions for acceptable security findings in demo/dev environment"""
        
        # Suppress AgentRole wildcard permissions
        NagSuppressions.add_resource_suppressions(
            self.bedrock_agent_role,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Bedrock agents require broad permissions for dynamic operations in demo/development environment",
                    "appliesTo": [
                        "Action::application-signals:*",
                        "Action::apprunner:*", 
                        "Action::bedrock-agentcore:*",
                        "Action::bedrock:*",
                        "Action::cloudwatch:*",
                        "Action::ecr-public:*",
                        "Action::kms:*",
                        "Action::secretsmanager:*",
                        "Action::xray:*",
                        "Action::s3:GetBucket*",
                        "Action::s3:GetObject*",
                        "Action::s3:List*",
                        "Resource::*",
                        "Resource::arn:aws:codebuild:*:*:build/*",
                        "Resource::arn:aws:ssm:*:*:parameter/*",
                        "Resource::arn:aws:logs:*:*:log-group:/aws/codebuild/*:*",
                        "Resource::arn:aws:codebuild:*:*:report-group/*"
                    ]
                }
            ]
        )
        
        # Suppress IAM findings for roles with AWS managed policies
        managed_policy_roles = [
            self.lambda_execution_role,
            self.apprunner_access_role, 
            self.codebuild_service_role
        ]
        
        for role in managed_policy_roles:
            NagSuppressions.add_resource_suppressions(
                role,
                [
                    {
                        "id": "AwsSolutions-IAM4",
                        "reason": "AWS managed policies acceptable for demo/development environment"
                    },
                    {
                        "id": "AwsSolutions-IAM5", 
                        "reason": "Wildcard permissions required for dynamic operations in demo/development environment"
                    }
                ]
            )
