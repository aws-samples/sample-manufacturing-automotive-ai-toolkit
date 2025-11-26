from aws_cdk import (
    Stack,
    Duration,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
    aws_s3_deployment as s3deploy,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_sns as sns,
    aws_ec2 as ec2,
    aws_logs as logs,
    aws_ssm as ssm,
    CfnOutput,
    RemovalPolicy
)
from constructs import Construct

class QualityInspectionStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, shared_resources=None, existing_vpc_id=None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Store shared resources
        self.shared_resources = shared_resources or {}
        self.existing_vpc_id = existing_vpc_id
        
        # Create unique suffix for resource names
        import hashlib
        unique_string = hashlib.md5(f"{self.account}-{self.region}-{construct_id}".encode()).hexdigest()[:8]
        self.unique_suffix = unique_string

        # Create or use existing VPC
        self.vpc = self.create_vpc()
        
        # Create DynamoDB tables
        self.create_dynamodb_tables()
        
        # Create S3 bucket with folder structure
        self.create_s3_infrastructure()
        
        # Create SNS topic
        self.create_sns_notifications()
        
        # Create CloudWatch log groups
        self.create_cloudwatch_logs()
        
        # Create model configuration parameters
        self.create_model_parameters()
        
        # Create AgentCore execution role
        self.agentcore_role = self.create_agentcore_execution_role()
        
        # Create agent-specific policies
        self.create_agent_policies()
        
        # Note: AgentCore agents are deployed separately using quality_inspection_agentcore_deploy.sh
    
    def create_dynamodb_tables(self):
        """Create all DynamoDB tables for the multi-agent system"""
        tables_config = [
            "vision-inspection-data",
            "sop-decisions", 
            "action-execution-log",
            "erp-integration-log",
            "historical-trends",
            "sap-integration-log"
        ]
        
        key_mappings = {
            "vision-inspection-data": "inspection_id",
            "sop-decisions": "decision_id",
            "action-execution-log": "execution_id", 
            "erp-integration-log": "integration_id",
            "historical-trends": "trend_id",
            "sap-integration-log": "sap_transaction_id"
        }
        
        for table_name in tables_config:
            dynamodb.Table(
                self, f"{table_name.replace('-', '')}Table",
                table_name=table_name,
                partition_key=dynamodb.Attribute(
                    name=key_mappings[table_name],
                    type=dynamodb.AttributeType.STRING
                ),
                billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
                removal_policy=RemovalPolicy.DESTROY
            )
    
    def create_s3_infrastructure(self):
        """Create S3 bucket with required folder structure"""
        bucket = s3.Bucket(
            self, "MachinepartimagesBucket",
            bucket_name=f"machinepartimages-{self.unique_suffix}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            encryption=s3.BucketEncryption.S3_MANAGED
        )
        
        # Upload reference image (relative to project root)
        import os
        project_root = os.path.dirname(os.path.dirname(__file__))
        reference_image_path = os.path.join(project_root, "tests", "test_images", "reference_image")
        
        s3deploy.BucketDeployment(
            self, "ReferenceImageDeployment",
            sources=[s3deploy.Source.asset(reference_image_path)],
            destination_bucket=bucket,
            destination_key_prefix="cleanimages/"
        )
        
        # Create Lambda function to trigger AgentCore orchestrator
        trigger_function = self.create_agentcore_trigger(bucket)
        
        # Output bucket name
        CfnOutput(self, "S3BucketName", value=bucket.bucket_name)
        
        return bucket
    
    def create_sns_notifications(self):
        """Create SNS topic without subscriptions"""
        topic = sns.Topic(
            self, "QualityInspectionAlerts",
            topic_name="quality-inspection-alerts"
        )
        
        # Output topic ARN
        CfnOutput(self, "SNSTopicArn", value=topic.topic_arn)
        
        return topic
    
    def create_vpc(self):
        """Create VPC with public and private subnets or use existing VPC"""
        if self.existing_vpc_id:
            # Use existing VPC
            vpc = ec2.Vpc.from_lookup(
                self, "ExistingVpc",
                vpc_id=self.existing_vpc_id
            )
        else:
            # Create new VPC
            vpc = ec2.Vpc(
                self, "AgenticQualityInspectionVpc",
                vpc_name="vpc-agentic-quality-inspection",
                ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
                max_azs=2,
                subnet_configuration=[
                    ec2.SubnetConfiguration(
                        name="subnet-vpc-agentic-quality-inspection-public",
                        subnet_type=ec2.SubnetType.PUBLIC,
                        cidr_mask=24
                    ),
                    ec2.SubnetConfiguration(
                        name="subnet-vpc-agentic-quality-inspection-private",
                        subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                        cidr_mask=24
                    )
                ],
                nat_gateways=2
            )
        
        # Create security group for AgentCore
        agentcore_sg = ec2.SecurityGroup(
            self, "BedrockAgentCoreSecurityGroup",
            vpc=vpc,
            description="Security group for Bedrock AgentCore agents",
            allow_all_outbound=True
        )
        
        # Allow HTTPS traffic within VPC
        agentcore_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(443),
            description="HTTPS from VPC"
        )
        
        # Output VPC details for AgentCore
        CfnOutput(self, "VpcId", value=vpc.vpc_id)
        if vpc.private_subnets:
            CfnOutput(self, "PrivateSubnet1Id", value=vpc.private_subnets[0].subnet_id)
            if len(vpc.private_subnets) > 1:
                CfnOutput(self, "PrivateSubnet2Id", value=vpc.private_subnets[1].subnet_id)
        CfnOutput(self, "BedrockAgentCoreSecurityGroupId", value=agentcore_sg.security_group_id)
        
        return vpc
    
    def create_cloudwatch_logs(self):
        """Create CloudWatch log groups for all components"""
        log_groups = [
            "quality-inspection-vision-agent",
            "quality-inspection-sop-agent", 
            "quality-inspection-action-agent",
            "quality-inspection-communication-agent",
            "quality-inspection-analysis-agent",
            "quality-inspection-batch-processor",
            "quality-inspection-streamlit-app"
        ]
        
        for log_group_name in log_groups:
            logs.LogGroup(
                self, f"{log_group_name.replace('-', '')}LogGroup",
                log_group_name=f"/aws/quality-inspection/{log_group_name}",
                removal_policy=RemovalPolicy.DESTROY,
                retention=logs.RetentionDays.ONE_MONTH
            )
    
    def create_agentcore_trigger(self, bucket):
        """Create Lambda function to trigger AgentCore orchestrator on S3 events"""
        
        # Create IAM role for the trigger function
        trigger_role = iam.Role(
            self, "AgentCoreTriggerRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "AgentCoreAccessPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "bedrock-agentcore:InvokeAgentRuntime",
                                "bedrock-agentcore:GetAgentRuntime",
                                "bedrock-agentcore:ListAgentRuntimes"
                            ],
                            resources=[
                                f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:runtime/*",
                                f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:agent-runtime/*"
                            ]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "ssm:GetParameter",
                                "ssm:GetParameters"
                            ],
                            resources=[
                                f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/primary-model/model-id",
                                f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/secondary-model/model-id",
                                f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/agentcore-runtime/orchestrator"
                            ]
                        )
                    ]
                )
            }
        )
        
        # Create the trigger function - it will find orchestrator ARN dynamically
        import os
        project_root = os.path.dirname(os.path.dirname(__file__))
        lambda_code_path = os.path.join(project_root, "src", "lambda_functions")
        
        trigger_function = _lambda.Function(
            self, "QualityInspectionAgentTrigger",
            function_name="quality-inspection-agent-trigger",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="quality-inspection-agent-trigger.lambda_handler",
            code=_lambda.Code.from_asset(lambda_code_path),
            role=trigger_role,
            timeout=Duration.minutes(5)
            # No environment variables needed - Lambda will determine orchestrator ARN dynamically
        )
        
        # Output the Lambda function name for reference
        CfnOutput(self, "TriggerFunctionName", value=trigger_function.function_name)
        
        # Add S3 trigger
        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(trigger_function),
            s3.NotificationKeyFilter(prefix="inputimages/")
        )
        
        return trigger_function
    
    def create_agentcore_execution_role(self):
        """Create IAM role for AgentCore agents with necessary permissions"""
        agentcore_role = iam.Role(
            self, "AgentCoreExecutionRole",
            role_name=f"QualityInspectionAgentCoreRole-{self.unique_suffix}",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "AgentCorePermissions": iam.PolicyDocument(
                    statements=[
                        # SSM Parameter Store access
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "ssm:GetParameter",
                                "ssm:GetParameters"
                            ],
                            resources=[
                                f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/primary-model/model-id",
                                f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/secondary-model/model-id",
                                f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/reference-image-s3-uri",
                                f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/agentcore-runtime/*"
                            ]
                        ),
                        # Bedrock model access
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "bedrock:InvokeModel",
                                "bedrock:InvokeModelWithResponseStream",
                                "bedrock:Converse",
                                "bedrock:ConverseStream"
                            ],
                            resources=[
                                f"arn:aws:bedrock:{self.region}::foundation-model/us.amazon.nova-pro-v1:0",
                                f"arn:aws:bedrock:{self.region}::foundation-model/*"
                            ]
                        ),
                        # ECR access for AgentCore
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "ecr:GetAuthorizationToken",
                                "ecr:BatchGetImage",
                                "ecr:GetDownloadUrlForLayer"
                            ],
                            resources=["*"]
                        ),
                        # S3 access for images
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:DeleteObject"
                            ],
                            resources=[
                                f"arn:aws:s3:::machinepartimages-{self.unique_suffix}/*"
                            ]
                        ),
                        # DynamoDB access
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "dynamodb:PutItem",
                                "dynamodb:GetItem",
                                "dynamodb:UpdateItem",
                                "dynamodb:Scan",
                                "dynamodb:Query"
                            ],
                            resources=[
                                f"arn:aws:dynamodb:{self.region}:{self.account}:table/vision-inspection-data",
                                f"arn:aws:dynamodb:{self.region}:{self.account}:table/sop-decisions",
                                f"arn:aws:dynamodb:{self.region}:{self.account}:table/action-execution-log",
                                f"arn:aws:dynamodb:{self.region}:{self.account}:table/erp-integration-log",
                                f"arn:aws:dynamodb:{self.region}:{self.account}:table/historical-trends",
                                f"arn:aws:dynamodb:{self.region}:{self.account}:table/sap-integration-log"
                            ]
                        )
                    ]
                )
            }
        )
        
        # Attach agent policies to the role (will be created after this role)
        # Note: These policies are attached via dependency in create_agent_policies method
        
        # Output role ARN for AgentCore configuration
        CfnOutput(self, "AgentCoreExecutionRoleArn", value=agentcore_role.role_arn)
        
        return agentcore_role
    
    def create_agent_policies(self):
        """Create customer managed policies for each AgentCore agent"""
        
        # Vision Agent Policy
        vision_policy = iam.ManagedPolicy(
            self, "QualityInspectionVisionAgentPolicy",
            managed_policy_name=f"QualityInspectionVisionAgentPolicy-{self.unique_suffix}",
            description="Permissions for Quality Inspection Vision Agent",
            document=iam.PolicyDocument(
                statements=[
                    # SSM Parameter Store access
                    iam.PolicyStatement(
                        sid="SSMParameterAccess",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "ssm:GetParameter",
                            "ssm:GetParameters"
                        ],
                        resources=[
                            f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/primary-model/model-id",
                            f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/secondary-model/model-id",
                            f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/reference-image-s3-uri",
                            f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/s3-bucket-name"
                        ]
                    ),
                    # Bedrock model access
                    iam.PolicyStatement(
                        sid="BedrockModelAccess",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "bedrock:InvokeModel",
                            "bedrock:InvokeModelWithResponseStream",
                            "bedrock:Converse",
                            "bedrock:ConverseStream"
                        ],
                        resources=[
                            f"arn:aws:bedrock:{self.region}::foundation-model/us.amazon.nova-pro-v1:0",
                            f"arn:aws:bedrock:{self.region}::foundation-model/*"
                        ]
                    ),
                    # S3 access for images
                    iam.PolicyStatement(
                        sid="S3ImageAccess",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "s3:GetObject",
                            "s3:PutObject",
                            "s3:DeleteObject",
                            "s3:ListBucket"
                        ],
                        resources=[
                            f"arn:aws:s3:::machinepartimages-{self.unique_suffix}",
                            f"arn:aws:s3:::machinepartimages-{self.unique_suffix}/*"
                        ]
                    ),
                    # DynamoDB access
                    iam.PolicyStatement(
                        sid="DynamoDBAccess",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "dynamodb:PutItem",
                            "dynamodb:GetItem",
                            "dynamodb:UpdateItem",
                            "dynamodb:Scan",
                            "dynamodb:Query"
                        ],
                        resources=[
                            f"arn:aws:dynamodb:{self.region}:{self.account}:table/vision-inspection-data"
                        ]
                    ),
                    # STS access for AgentCore
                    iam.PolicyStatement(
                        sid="STSAccess",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "sts:GetCallerIdentity"
                        ],
                        resources=["*"]
                    )
                ]
            )
        )
        
        # Orchestrator Agent Policy
        orchestrator_policy = iam.ManagedPolicy(
            self, "QualityInspectionOrchestratorAgentPolicy",
            managed_policy_name=f"QualityInspectionOrchestratorAgentPolicy-{self.unique_suffix}",
            description="Permissions for Quality Inspection Orchestrator Agent",
            document=iam.PolicyDocument(
                statements=[
                    # SSM Parameter Store access
                    iam.PolicyStatement(
                        sid="SSMParameterAccess",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "ssm:GetParameter",
                            "ssm:GetParameters"
                        ],
                        resources=[
                            f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/primary-model/model-id",
                            f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/secondary-model/model-id",
                            f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/reference-image-s3-uri",
                            f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/s3-bucket-name",
                            f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/agentcore-runtime/*"
                        ]
                    ),
                    # Bedrock model access for orchestrator
                    iam.PolicyStatement(
                        sid="BedrockModelAccess",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "bedrock:InvokeModel",
                            "bedrock:InvokeModelWithResponseStream",
                            "bedrock:Converse",
                            "bedrock:ConverseStream"
                        ],
                        resources=[
                            f"arn:aws:bedrock:{self.region}::foundation-model/us.amazon.nova-pro-v1:0",
                            f"arn:aws:bedrock:{self.region}::foundation-model/*"
                        ]
                    ),
                    # S3 access for file operations
                    iam.PolicyStatement(
                        sid="S3FileOperations",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "s3:GetObject",
                            "s3:PutObject",
                            "s3:DeleteObject",
                            "s3:ListBucket"
                        ],
                        resources=[
                            f"arn:aws:s3:::machinepartimages-{self.unique_suffix}",
                            f"arn:aws:s3:::machinepartimages-{self.unique_suffix}/*"
                        ]
                    ),
                    # DynamoDB access for all tables
                    iam.PolicyStatement(
                        sid="DynamoDBAccess",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "dynamodb:PutItem",
                            "dynamodb:GetItem",
                            "dynamodb:UpdateItem",
                            "dynamodb:Scan",
                            "dynamodb:Query"
                        ],
                        resources=[
                            f"arn:aws:dynamodb:{self.region}:{self.account}:table/vision-inspection-data",
                            f"arn:aws:dynamodb:{self.region}:{self.account}:table/sop-decisions",
                            f"arn:aws:dynamodb:{self.region}:{self.account}:table/action-execution-log",
                            f"arn:aws:dynamodb:{self.region}:{self.account}:table/erp-integration-log",
                            f"arn:aws:dynamodb:{self.region}:{self.account}:table/historical-trends",
                            f"arn:aws:dynamodb:{self.region}:{self.account}:table/sap-integration-log"
                        ]
                    ),
                    # AgentCore invocation for calling other agents
                    iam.PolicyStatement(
                        sid="AgentCoreInvocation",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "bedrock-agentcore:InvokeAgentRuntime",
                            "bedrock-agentcore:InvokeAgentRuntimeForUser",
                            "bedrock-agentcore-control:ListAgentRuntimes",
                            "bedrock-agentcore-control:GetAgentRuntime"
                        ],
                        resources=[
                            f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:runtime/*",
                            "*"
                        ]
                    )
                ]
            )
        )
        
        # Analysis Agent Policy
        analysis_policy = iam.ManagedPolicy(
            self, "QualityInspectionAnalysisAgentPolicy",
            managed_policy_name=f"QualityInspectionAnalysisAgentPolicy-{self.unique_suffix}",
            description="Permissions for Quality Inspection Analysis Agent",
            document=iam.PolicyDocument(
                statements=[
                    # SSM Parameter Store access
                    iam.PolicyStatement(
                        sid="SSMParameterAccess",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "ssm:GetParameter",
                            "ssm:GetParameters"
                        ],
                        resources=[
                            f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/primary-model/model-id",
                            f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/secondary-model/model-id",
                            f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/s3-bucket-name"
                        ]
                    ),
                    # DynamoDB access for trend analysis
                    iam.PolicyStatement(
                        sid="DynamoDBAccess",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "dynamodb:PutItem",
                            "dynamodb:GetItem",
                            "dynamodb:UpdateItem",
                            "dynamodb:Scan",
                            "dynamodb:Query"
                        ],
                        resources=[
                            f"arn:aws:dynamodb:{self.region}:{self.account}:table/vision-inspection-data",
                            f"arn:aws:dynamodb:{self.region}:{self.account}:table/historical-trends"
                        ]
                    )
                ]
            )
        )
        
        # SOP Agent Policy
        sop_policy = iam.ManagedPolicy(
            self, "QualityInspectionSOPAgentPolicy",
            managed_policy_name=f"QualityInspectionSOPAgentPolicy-{self.unique_suffix}",
            description="Permissions for Quality Inspection SOP Agent",
            document=iam.PolicyDocument(
                statements=[
                    # SSM Parameter Store access
                    iam.PolicyStatement(
                        sid="SSMParameterAccess",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "ssm:GetParameter",
                            "ssm:GetParameters"
                        ],
                        resources=[
                            f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/primary-model/model-id",
                            f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/secondary-model/model-id",
                            f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/s3-bucket-name"
                        ]
                    ),
                    # DynamoDB access for SOP decisions
                    iam.PolicyStatement(
                        sid="DynamoDBAccess",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "dynamodb:PutItem",
                            "dynamodb:GetItem",
                            "dynamodb:UpdateItem"
                        ],
                        resources=[
                            f"arn:aws:dynamodb:{self.region}:{self.account}:table/sop-decisions"
                        ]
                    )
                ]
            )
        )
        
        # Action Agent Policy
        action_policy = iam.ManagedPolicy(
            self, "QualityInspectionActionAgentPolicy",
            managed_policy_name=f"QualityInspectionActionAgentPolicy-{self.unique_suffix}",
            description="Permissions for Quality Inspection Action Agent",
            document=iam.PolicyDocument(
                statements=[
                    # SSM Parameter Store access
                    iam.PolicyStatement(
                        sid="SSMParameterAccess",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "ssm:GetParameter",
                            "ssm:GetParameters"
                        ],
                        resources=[
                            f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/primary-model/model-id",
                            f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/secondary-model/model-id",
                            f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/s3-bucket-name"
                        ]
                    ),
                    # S3 access for file operations
                    iam.PolicyStatement(
                        sid="S3FileOperations",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "s3:GetObject",
                            "s3:PutObject",
                            "s3:DeleteObject",
                            "s3:ListBucket"
                        ],
                        resources=[
                            f"arn:aws:s3:::machinepartimages-{self.unique_suffix}",
                            f"arn:aws:s3:::machinepartimages-{self.unique_suffix}/*"
                        ]
                    ),
                    # DynamoDB access for action logs
                    iam.PolicyStatement(
                        sid="DynamoDBAccess",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "dynamodb:PutItem",
                            "dynamodb:GetItem",
                            "dynamodb:UpdateItem"
                        ],
                        resources=[
                            f"arn:aws:dynamodb:{self.region}:{self.account}:table/action-execution-log"
                        ]
                    )
                ]
            )
        )
        
        # Communication Agent Policy
        communication_policy = iam.ManagedPolicy(
            self, "QualityInspectionCommunicationAgentPolicy",
            managed_policy_name=f"QualityInspectionCommunicationAgentPolicy-{self.unique_suffix}",
            description="Permissions for Quality Inspection Communication Agent",
            document=iam.PolicyDocument(
                statements=[
                    # SSM Parameter Store access
                    iam.PolicyStatement(
                        sid="SSMParameterAccess",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "ssm:GetParameter",
                            "ssm:GetParameters"
                        ],
                        resources=[
                            f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/primary-model/model-id",
                            f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/secondary-model/model-id",
                            f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/s3-bucket-name"
                        ]
                    ),
                    # SNS access for notifications
                    iam.PolicyStatement(
                        sid="SNSNotifications",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "sns:Publish"
                        ],
                        resources=[
                            f"arn:aws:sns:{self.region}:{self.account}:quality-inspection-alerts"
                        ]
                    ),
                    # DynamoDB access for communication logs
                    iam.PolicyStatement(
                        sid="DynamoDBAccess",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "dynamodb:PutItem",
                            "dynamodb:GetItem",
                            "dynamodb:UpdateItem"
                        ],
                        resources=[
                            f"arn:aws:dynamodb:{self.region}:{self.account}:table/erp-integration-log",
                            f"arn:aws:dynamodb:{self.region}:{self.account}:table/sap-integration-log"
                        ]
                    )
                ]
            )
        )
        
        # Attach policies to the AgentCore execution role
        self.agentcore_role.add_managed_policy(vision_policy)
        self.agentcore_role.add_managed_policy(orchestrator_policy)
        self.agentcore_role.add_managed_policy(analysis_policy)
        self.agentcore_role.add_managed_policy(sop_policy)
        self.agentcore_role.add_managed_policy(action_policy)
        self.agentcore_role.add_managed_policy(communication_policy)
        
        # Output policy ARNs for reference
        CfnOutput(self, "VisionAgentPolicyArn", value=vision_policy.managed_policy_arn)
        CfnOutput(self, "OrchestratorAgentPolicyArn", value=orchestrator_policy.managed_policy_arn)
        CfnOutput(self, "AnalysisAgentPolicyArn", value=analysis_policy.managed_policy_arn)
        CfnOutput(self, "SOPAgentPolicyArn", value=sop_policy.managed_policy_arn)
        CfnOutput(self, "ActionAgentPolicyArn", value=action_policy.managed_policy_arn)
        CfnOutput(self, "CommunicationAgentPolicyArn", value=communication_policy.managed_policy_arn)
        
        return {
            'vision': vision_policy,
            'orchestrator': orchestrator_policy,
            'analysis': analysis_policy,
            'sop': sop_policy,
            'action': action_policy,
            'communication': communication_policy
        }
    
    def create_model_parameters(self):
        """Create SSM parameters for model configuration"""
        # Primary model parameter
        ssm.StringParameter(
            self, "PrimaryModelParameter",
            parameter_name="/quality-inspection/primary-model/model-id",
            string_value="us.amazon.nova-pro-v1:0",
            description="Primary model ID for quality inspection agents"
        )
        
        # Secondary model parameter
        ssm.StringParameter(
            self, "SecondaryModelParameter",
            parameter_name="/quality-inspection/secondary-model/model-id",
            string_value="us.amazon.nova-pro-v1:0",
            description="Secondary/fallback model ID for quality inspection agents"
        )
        
        # S3 bucket name parameter
        ssm.StringParameter(
            self, "S3BucketNameParameter",
            parameter_name="/quality-inspection/s3-bucket-name",
            string_value=f"machinepartimages-{self.unique_suffix}",
            description="S3 bucket name for quality inspection images"
        )
        
        # Reference image S3 URI parameter
        ssm.StringParameter(
            self, "ReferenceImageS3UriParameter",
            parameter_name="/quality-inspection/reference-image-s3-uri",
            string_value=f"s3://machinepartimages-{self.unique_suffix}/cleanimages/Cleanimage.jpg",
            description="S3 URI for the reference clean image used in quality inspection"
        )
        
        # AgentCore runtime ARN parameters (empty initially, to be populated after deployment)
        ssm.StringParameter(
            self, "VisionAgentRuntimeArnParameter",
            parameter_name="/quality-inspection/agentcore-runtime/vision",
            string_value="PLACEHOLDER",
            description="Vision agent runtime ARN - update after AgentCore deployment"
        )
        
        ssm.StringParameter(
            self, "AnalysisAgentRuntimeArnParameter",
            parameter_name="/quality-inspection/agentcore-runtime/analysis",
            string_value="PLACEHOLDER",
            description="Analysis agent runtime ARN - update after AgentCore deployment"
        )
        
        ssm.StringParameter(
            self, "SOPAgentRuntimeArnParameter",
            parameter_name="/quality-inspection/agentcore-runtime/sop",
            string_value="PLACEHOLDER",
            description="SOP agent runtime ARN - update after AgentCore deployment"
        )
        
        ssm.StringParameter(
            self, "ActionAgentRuntimeArnParameter",
            parameter_name="/quality-inspection/agentcore-runtime/action",
            string_value="PLACEHOLDER",
            description="Action agent runtime ARN - update after AgentCore deployment"
        )
        
        ssm.StringParameter(
            self, "CommunicationAgentRuntimeArnParameter",
            parameter_name="/quality-inspection/agentcore-runtime/communication",
            string_value="PLACEHOLDER",
            description="Communication agent runtime ARN - update after AgentCore deployment"
        )
        
        ssm.StringParameter(
            self, "OrchestratorAgentRuntimeArnParameter",
            parameter_name="/quality-inspection/agentcore-runtime/orchestrator",
            string_value="PLACEHOLDER",
            description="Orchestrator agent runtime ARN - update after AgentCore deployment"
        )
        
        # Output parameter names
        CfnOutput(self, "PrimaryModelParameterName", value="/quality-inspection/primary-model/model-id")
        CfnOutput(self, "SecondaryModelParameterName", value="/quality-inspection/secondary-model/model-id")
        CfnOutput(self, "ReferenceImageS3UriParameterName", value="/quality-inspection/reference-image-s3-uri")
    

    
