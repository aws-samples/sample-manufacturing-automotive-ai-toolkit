from aws_cdk import (
    Stack,
    NestedStack,
    Duration,
    PhysicalName,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
    aws_s3_deployment as s3deploy,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    aws_ec2 as ec2,
    aws_logs as logs,
    aws_ssm as ssm,

    aws_s3_assets as s3_assets,
    aws_bedrockagentcore as bedrockagentcore,
    CfnOutput,
    RemovalPolicy
)
from constructs import Construct

class QualityInspectionStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Using EventBridge automation for universal compatibility
        
        # Create VPC
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
            bucket_name=PhysicalName.GENERATE_IF_NEEDED,
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
            topic_name="quality-inspection-alerts",
            master_key=None  # Use AWS managed encryption
        )
        
        # Output topic ARN
        CfnOutput(self, "SNSTopicArn", value=topic.topic_arn)
        
        return topic
    
    def create_vpc(self):
        """Create VPC with public and private subnets"""
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
        
        # Output VPC details for AgentCore (only add new outputs)
        CfnOutput(self, "PrivateSubnet1Id", value=vpc.private_subnets[0].subnet_id)
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
        
        import os
        project_root = os.path.dirname(os.path.dirname(__file__))
        
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
        trigger_function = _lambda.Function(
            self, "QualityInspectionAgentTrigger",
            function_name="quality-inspection-agent-trigger",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="quality-inspection-agent-trigger.lambda_handler",
            code=_lambda.Code.from_asset(os.path.join(project_root, "src", "lambda_functions")),
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
    

    
    def create_model_parameters(self):
        """Create SSM parameters for model configuration"""
        # Primary model parameter
        ssm.StringParameter(
            self, "PrimaryModelParameter",
            parameter_name="/quality-inspection/primary-model/model-id",
            string_value="amazon.nova-pro-v1:0",
            description="Primary model ID for quality inspection agents"
        )
        
        # Secondary model parameter
        ssm.StringParameter(
            self, "SecondaryModelParameter",
            parameter_name="/quality-inspection/secondary-model/model-id",
            string_value="amazon.nova-pro-v1:0",
            description="Secondary/fallback model ID for quality inspection agents"
        )
        
        # Reference image S3 URI parameter
        ssm.StringParameter(
            self, "ReferenceImageS3UriParameter",
            parameter_name="/quality-inspection/reference-image-s3-uri",
            string_value=f"s3://machinepartimages-{self.account}/cleanimages/Cleanimage.jpg",
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
    

    
