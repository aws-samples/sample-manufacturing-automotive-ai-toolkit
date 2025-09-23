"""
IAM Construct for roles and policies
"""

from aws_cdk import (
    aws_iam as iam,
    aws_s3 as s3,
    Tags,
    Stack,
)
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

        # Create CodeBuild service role
        self._create_codebuild_service_role()

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

        # Add Bedrock permissions
        self._add_bedrock_permissions()

        # Add ECR permissions
        self._add_ecr_permissions()

        # Add Bedrock AgentCore permissions
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

    def _add_bedrock_permissions(self) -> None:
        """Add Bedrock-specific permissions to the agent role"""

        # Foundation model permissions
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:GetFoundationModel",
                    "bedrock:ListFoundationModels"
                ],
                resources=[
                    f"arn:{Stack.of(self).partition}:bedrock:*::foundation-model/*"
                ]
            )
        )

        # Agent management permissions
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:CreateAgent",
                    "bedrock:UpdateAgent",
                    "bedrock:GetAgent",
                    "bedrock:ListAgents",
                    "bedrock:DeleteAgent",
                    "bedrock:CreateAgentAlias",
                    "bedrock:UpdateAgentAlias",
                    "bedrock:GetAgentAlias",
                    "bedrock:ListAgentAliases",
                    "bedrock:DeleteAgentAlias",
                    "bedrock:PrepareAgent"
                ],
                resources=[
                    f"arn:{Stack.of(self).partition}:bedrock:{Stack.of(self).region}:{Stack.of(self).account}:agent/*",
                    f"arn:{Stack.of(self).partition}:bedrock:{Stack.of(self).region}:{Stack.of(self).account}:agent-alias/*"
                ]
            )
        )

        # Knowledge base permissions
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:CreateKnowledgeBase",
                    "bedrock:UpdateKnowledgeBase",
                    "bedrock:GetKnowledgeBase",
                    "bedrock:ListKnowledgeBases",
                    "bedrock:DeleteKnowledgeBase",
                    "bedrock:AssociateAgentKnowledgeBase",
                    "bedrock:DisassociateAgentKnowledgeBase"
                ],
                resources=[
                    f"arn:{Stack.of(self).partition}:bedrock:{Stack.of(self).region}:{Stack.of(self).account}:knowledge-base/*"
                ]
            )
        )

        # Inference profile permissions
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:GetInferenceProfile",
                    "bedrock:ListInferenceProfiles"
                ],
                resources=[
                    f"arn:{Stack.of(self).partition}:bedrock:{Stack.of(self).region}:{Stack.of(self).account}:inference-profile/*",
                    f"arn:{Stack.of(self).partition}:bedrock:{Stack.of(self).region}:{Stack.of(self).account}:application-inference-profile/*"
                ]
            )
        )

        # Guardrail permissions
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:GetGuardrail",
                    "bedrock:ListGuardrails"
                ],
                resources=[
                    f"arn:{Stack.of(self).partition}:bedrock:{Stack.of(self).region}:{Stack.of(self).account}:guardrail/*"
                ]
            )
        )

    def _add_ecr_permissions(self) -> None:
        """Add ECR permissions to the agent role"""

        # ECR authorization token
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ecr:GetAuthorizationToken"],
                resources=["*"]
            )
        )

        # ECR repository operations
        self.bedrock_agent_role.add_to_policy(
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

    def _add_bedrock_agentcore_permissions(self) -> None:
        """Add Bedrock AgentCore permissions to the agent role"""
        self.bedrock_agent_role.add_to_policy(
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
                resources=[
                    f"arn:aws:bedrock-agentcore:{Stack.of(self).region}:{Stack.of(self).account}:agent/*"
                ]
            )
        )

    def _add_s3_permissions(self) -> None:
        """Add S3 permissions to the agent role"""
        if self.resource_bucket:
            self.bedrock_agent_role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "s3:GetObject",
                        "s3:GetObjectVersion",
                        "s3:ListBucket"
                    ],
                    resources=[
                        self.resource_bucket.bucket_arn,
                        f"{self.resource_bucket.bucket_arn}/*"
                    ]
                )
            )

    def _add_cloudwatch_logs_permissions(self) -> None:
        """Add CloudWatch Logs permissions to the agent role"""
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=[
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/codebuild/{Stack.of(self).stack_name}-*",
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/lambda/*",
                    f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/bedrock/*"
                ]
            )
        )

    def _add_ssm_permissions(self) -> None:
        """Add SSM permissions to the agent role"""
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ssm:GetParameter"],
                resources=[
                    f"arn:aws:ssm:{Stack.of(self).region}:{Stack.of(self).account}:parameter/*"
                ]
            )
        )

    def _add_iam_passrole_permissions(self) -> None:
        """Add IAM PassRole permissions to the agent role"""
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["iam:PassRole"],
                resources=[
                    f"arn:aws:iam::{Stack.of(self).account}:role/{Stack.of(self).stack_name}-AgentRole-*"
                ],
                conditions={
                    "StringEquals": {
                        "iam:PassedToService": [
                            "bedrock-agentcore.amazonaws.com",
                            "bedrock.amazonaws.com"
                        ]
                    }
                }
            )
        )
        
        # Add IAM permissions needed by AgentCore toolkit
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "iam:GetRole",
                    "iam:CreateRole",
                    "iam:AttachRolePolicy",
                    "iam:DetachRolePolicy",
                    "iam:PutRolePolicy",
                    "iam:DeleteRolePolicy",
                    "iam:ListRolePolicies",
                    "iam:ListAttachedRolePolicies"
                ],
                resources=[
                    f"arn:aws:iam::{Stack.of(self).account}:role/AmazonBedrockAgentCoreSDK*",
                    f"arn:aws:iam::{Stack.of(self).account}:role/{Stack.of(self).stack_name}-*"
                ]
            )
        )
        
        # Add CodeBuild permissions needed by AgentCore toolkit
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "codebuild:CreateProject",
                    "codebuild:UpdateProject",
                    "codebuild:DeleteProject",
                    "codebuild:StartBuild",
                    "codebuild:BatchGetBuilds",
                    "codebuild:BatchGetProjects"
                ],
                resources=[
                    f"arn:aws:codebuild:{Stack.of(self).region}:{Stack.of(self).account}:project/bedrock-agentcore-*"
                ]
            )
        )
        
        # Add S3 bucket creation permissions needed by AgentCore toolkit
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:CreateBucket",
                    "s3:DeleteBucket",
                    "s3:GetBucketLocation",
                    "s3:ListBucket",
                    "s3:PutBucketPolicy",
                    "s3:GetBucketPolicy",
                    "s3:DeleteBucketPolicy"
                ],
                resources=[
                    f"arn:aws:s3:::bedrock-agentcore-*"
                ]
            )
        )
        
        # Add S3 object permissions for AgentCore toolkit buckets
        self.bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket"
                ],
                resources=[
                    f"arn:aws:s3:::bedrock-agentcore-*/*"
                ]
            )
        )

    def _apply_tags(self) -> None:
        """Apply consistent tags to all IAM resources"""
        Tags.of(self.bedrock_agent_role).add("Project", "ma3t-agents-toolkit")
        Tags.of(self.lambda_execution_role).add(
            "Project", "ma3t-agents-toolkit")
        Tags.of(self.codebuild_service_role).add(
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
