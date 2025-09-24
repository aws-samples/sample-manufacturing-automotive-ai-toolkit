import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_iam as iam,
    aws_codebuild as codebuild,
    CfnParameter,
    CfnOutput
)
from constructs import Construct

class Ma3tStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Parameters
        bedrock_model_id = CfnParameter(
            self, "BedrockModelId",
            type="String",
            description="The Bedrock model ID to use for the agents",
            default="anthropic.claude-3-haiku-20240307-v1:0"
        )

        s3_bucket_name = CfnParameter(
            self, "S3BucketName", 
            type="String",
            description="Name of the S3 bucket to use for code storage",
            default=""
        )

        # S3 Bucket
        bucket = s3.Bucket(
            self, "S3Bucket",
            bucket_name=f"ma3t-toolkit-{self.account}-{self.region}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=cdk.RemovalPolicy.RETAIN
        )

        # IAM Role - simplified based on CodeBuild best practices
        agent_role = iam.Role(
            self, "AgentRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("codebuild.amazonaws.com"),
                iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
                iam.ServicePrincipal("bedrock.amazonaws.com")
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "CodeBuildServiceRolePolicy": iam.PolicyDocument(
                    statements=[
                        # Basic CodeBuild permissions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream", 
                                "logs:PutLogEvents"
                            ],
                            resources=["*"]
                        ),
                        # S3 permissions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:GetObject",
                                "s3:GetObjectVersion",
                                "s3:PutObject",
                                "s3:GetBucketAcl",
                                "s3:GetBucketLocation",
                                "s3:ListBucket",
                                "s3:CreateBucket",
                                "s3:PutBucketPolicy"
                            ],
                            resources=["*"]
                        ),
                        # ECR permissions
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
                        ),
                        # Bedrock permissions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "bedrock:*",
                                "bedrock-agentcore:*"
                            ],
                            resources=["*"]
                        ),
                        # IAM permissions for AgentCore
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
                        ),
                        # CodeBuild permissions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "codebuild:CreateProject",
                                "codebuild:UpdateProject",
                                "codebuild:StartBuild",
                                "codebuild:BatchGetBuilds"
                            ],
                            resources=["*"]
                        ),
                        # Additional services
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "sts:GetServiceBearerToken",
                                "secretsmanager:*",
                                "kms:*",
                                "lambda:ListFunctions",
                                "application-signals:*",
                                "cloudwatch:*",
                                "xray:*"
                            ],
                            resources=["*"]
                        )
                    ]
                )
            }
        )

        # CodeBuild Project for AgentCore deployment
        agentcore_project = codebuild.Project(
            self, "AgentCoreProject",
            project_name=f"{self.stack_name}-agent-deployment",
            role=agent_role,
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxArmBuildImage.AMAZON_LINUX_2_STANDARD_3_0,
                compute_type=codebuild.ComputeType.SMALL,
                environment_variables={
                    "EXECUTION_ROLE_ARN": codebuild.BuildEnvironmentVariable(value=agent_role.role_arn),
                    "AWS_REGION": codebuild.BuildEnvironmentVariable(value=self.region)
                }
            ),
            source=codebuild.Source.s3(
                bucket=bucket,
                path="repo"
            ),
            build_spec=codebuild.BuildSpec.from_source_filename("build/codebuild_agentcore.yml"),
            # No artifacts needed
        )

        # Outputs
        CfnOutput(
            self, "AgentRoleArn",
            value=agent_role.role_arn,
            description="Amazon Bedrock Service Role ARN"
        )

        CfnOutput(
            self, "AgentCoreDeploymentProject",
            value=agentcore_project.project_name,
            description="CodeBuild project for deploying AgentCore agents"
        )

        CfnOutput(
            self, "S3BucketNameOutput",
            value=bucket.bucket_name,
            description="S3 bucket name used for code storage"
        )
