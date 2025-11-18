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
    aws_events as events,
    aws_events_targets as targets,
    aws_s3_assets as s3_assets,
    aws_bedrockagentcore as bedrockagentcore,
    CfnOutput,
    RemovalPolicy
)
from constructs import Construct

class QualityInspectionStack(NestedStack):
    def __init__(self, scope: Construct, construct_id: str, shared_resources=None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Store shared resources
        self.shared_resources = shared_resources or {}
        
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
        
        # Create Lambda trigger function
        self.create_agentcore_trigger()
        
        # Deploy custom UI if shared resources available
        if self.shared_resources:
            self.deploy_custom_ui()
    
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
        
        # Output bucket name (multiple formats for compatibility)
        CfnOutput(self, "S3BucketName", value=bucket.bucket_name)
        CfnOutput(self, "BucketName", value=bucket.bucket_name)
        CfnOutput(self, "MachinepartimagesBucketName", value=bucket.bucket_name)
        # Main output expected by deploy_cdk.sh
        CfnOutput(self, "ResourceBucketName", value=bucket.bucket_name)
        
        # Store bucket for use in model parameters
        self.bucket = bucket
        
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
        # Use shared Lambda execution role from main stack
        lambda_role = self.shared_resources.get('lambda_execution_role')
        if not lambda_role:
            print("Warning: No shared lambda execution role found, trigger function may not work properly")
            return None

        project_root = os.path.dirname(os.path.dirname(__file__))

        # Create the trigger function using shared role
        trigger_function = _lambda.Function(
            self, "QualityInspectionAgentTrigger",
            function_name="quality-inspection-agent-trigger",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="quality-inspection-agent-trigger.lambda_handler",
            code=_lambda.Code.from_asset(os.path.join(project_root, "src", "lambda_functions")),
            role=lambda_role,
            timeout=Duration.minutes(5)
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
        
        # Reference image S3 URI parameter (using actual bucket name)
        ssm.StringParameter(
            self, "ReferenceImageS3UriParameter",
            parameter_name="/quality-inspection/reference-image-s3-uri",
            string_value=f"s3://{self.bucket.bucket_name}/cleanimages/Cleanimage.jpg",
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
    
    def create_agentcore_codebuild_project(self):
        """Create a CodeBuild project for AgentCore deployment"""
        
        import os
        from aws_cdk import aws_codebuild as codebuild
        
        # Create IAM role for CodeBuild
        codebuild_role = iam.Role(
            self, "QualityInspectionCodeBuildRole",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
            inline_policies={
                "AgentCoreDeploymentPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents"
                            ],
                            resources=[f"arn:aws:logs:{self.region}:{self.account}:*"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "bedrock-agentcore:*",
                                "ecr:*",
                                "iam:PassRole",
                                "iam:GetRole",
                                "iam:CreateRole",
                                "iam:DeleteRole",
                                "iam:AttachRolePolicy",
                                "iam:DetachRolePolicy",
                                "iam:ListAttachedRolePolicies",
                                "iam:TagRole",
                                "iam:UntagRole",
                                "iam:ListRoleTags",
                                "iam:PutRolePolicy",
                                "iam:DeleteRolePolicy",
                                "iam:GetRolePolicy",
                                "iam:ListRolePolicies",
                                "iam:CreateServiceLinkedRole",
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:DeleteObject",
                                "s3:ListBucket",
                                "s3:CreateBucket",
                                "s3:GetBucketLocation",
                                "codebuild:*",
                                "lambda:*",
                                "application-autoscaling:*",
                                "cloudformation:*"
                            ],
                            resources=["*"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "ssm:PutParameter",
                                "ssm:GetParameter",
                                "ssm:GetParameters"
                            ],
                            resources=[
                                f"arn:aws:ssm:{self.region}:{self.account}:parameter/quality-inspection/agentcore-runtime/*"
                            ]
                        )
                    ]
                )
            }
        )
        
        # Create a dedicated CodeBuild role for AgentCore with all necessary permissions
        agentcore_codebuild_role = iam.Role(
            self, "AgentCoreCodeBuildRole",
            role_name=f"AgentCoreCodeBuildRole-{self.region}",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
            inline_policies={
                "AgentCoreCodeBuildPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents"
                            ],
                            resources=["*"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "ecr:BatchCheckLayerAvailability",
                                "ecr:GetDownloadUrlForLayer",
                                "ecr:BatchGetImage",
                                "ecr:GetAuthorizationToken",
                                "ecr:PutImage",
                                "ecr:InitiateLayerUpload",
                                "ecr:UploadLayerPart",
                                "ecr:CompleteLayerUpload",
                                "ecr:CreateRepository",
                                "ecr:DescribeRepositories"
                            ],
                            resources=["*"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "bedrock-agentcore:*"
                            ],
                            resources=["*"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:DeleteObject",
                                "s3:ListBucket",
                                "s3:CreateBucket",
                                "s3:GetBucketLocation"
                            ],
                            resources=["*"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "iam:PassRole",
                                "iam:GetRole",
                                "iam:CreateRole",
                                "iam:DeleteRole",
                                "iam:AttachRolePolicy",
                                "iam:DetachRolePolicy",
                                "iam:ListAttachedRolePolicies",
                                "iam:TagRole",
                                "iam:UntagRole",
                                "iam:ListRoleTags",
                                "iam:PutRolePolicy",
                                "iam:DeleteRolePolicy",
                                "iam:GetRolePolicy",
                                "iam:ListRolePolicies"
                            ],
                            resources=["*"]
                        )
                    ]
                )
            }
        )
        

        
        # Create CodeBuild project for AgentCore deployment
        project = codebuild.Project(
            self, "QualityInspectionAgentCoreProject",
            project_name="quality-inspection-agentcore-deployment",
            role=codebuild_role,
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                compute_type=codebuild.ComputeType.SMALL
            ),
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "phases": {
                    "install": {
                        "runtime-versions": {
                            "python": "3.12"
                        },
                        "commands": [
                            "echo 'Installing AgentCore CLI'",
                            "pip install bedrock-agentcore-starter-toolkit"
                        ]
                    },
                    "build": {
                        "commands": [
                            "echo 'Deploying AgentCore agents'",
                            "echo 'Current directory:'",
                            "pwd",
                            "echo 'Listing contents:'",
                            "ls -la",
                            "echo 'Looking for quality inspection agents:'",
                            "find . -name '*quality*' -type d",
                            "cd agents_catalog/multi_agent_collaboration/02-quality_inspection_agentcore/src",
                            "echo 'In agent directory:'",
                            "pwd",
                            "ls -la",
                            "echo 'Checking for agent files:'",
                            "ls -la *.py",
                            "echo 'Installing agent requirements if they exist:'",
                            "if [ -f requirements.txt ]; then pip install -r requirements.txt; fi",
                            "echo 'Configuring agents with HTTP protocol for Strands and custom CodeBuild role'",
                            f"agentcore configure --entrypoint quality_inspection_orchestrator.py --name quality_inspection_orchestrator --protocol HTTP --non-interactive --disable-memory --code-build-execution-role {agentcore_codebuild_role.role_arn}",
                            f"agentcore configure --entrypoint vision_agent.py --name vision_agent --protocol HTTP --non-interactive --disable-memory --code-build-execution-role {agentcore_codebuild_role.role_arn}",
                            f"agentcore configure --entrypoint analysis_agent.py --name analysis_agent --protocol HTTP --non-interactive --disable-memory --code-build-execution-role {agentcore_codebuild_role.role_arn}",
                            f"agentcore configure --entrypoint sop_agent.py --name sop_agent --protocol HTTP --non-interactive --disable-memory --code-build-execution-role {agentcore_codebuild_role.role_arn}",
                            f"agentcore configure --entrypoint action_agent.py --name action_agent --protocol HTTP --non-interactive --disable-memory --code-build-execution-role {agentcore_codebuild_role.role_arn}",
                            f"agentcore configure --entrypoint communication_agent.py --name communication_agent --protocol HTTP --non-interactive --disable-memory --code-build-execution-role {agentcore_codebuild_role.role_arn}",
                            "echo 'Deploying orchestrator agent'",
                            "agentcore launch --agent quality_inspection_orchestrator --auto-update-on-conflict 2>&1 | tee orchestrator_output.txt",
                            "if [ $? -ne 0 ]; then echo 'Orchestrator launch failed - see output above'; exit 1; fi",
                            "cat orchestrator_output.txt",
                            "ORCHESTRATOR_ARN=$(grep -o 'arn:aws:bedrock-agentcore:[^:]*:[^:]*:runtime/[^[:space:]]*' orchestrator_output.txt | head -1)",
                            "echo \"Orchestrator ARN: $ORCHESTRATOR_ARN\"",
                            "if [ ! -z \"$ORCHESTRATOR_ARN\" ]; then aws ssm put-parameter --name '/quality-inspection/agentcore-runtime/orchestrator' --value \"$ORCHESTRATOR_ARN\" --type String --overwrite; fi",
                            "echo 'Deploying vision agent'",
                            "agentcore launch --agent vision_agent --auto-update-on-conflict 2>&1 | tee vision_output.txt",
                            "if [ $? -ne 0 ]; then echo 'Vision agent launch failed - see output above'; exit 1; fi",
                            "cat vision_output.txt",
                            "VISION_ARN=$(grep -o 'arn:aws:bedrock-agentcore:[^:]*:[^:]*:runtime/[^[:space:]]*' vision_output.txt | head -1)",
                            "echo \"Vision ARN: $VISION_ARN\"",
                            "if [ ! -z \"$VISION_ARN\" ]; then aws ssm put-parameter --name '/quality-inspection/agentcore-runtime/vision' --value \"$VISION_ARN\" --type String --overwrite; else echo 'No Vision ARN found, skipping SSM parameter'; fi",
                            "echo 'Deploying analysis agent'",
                            "agentcore launch --agent analysis_agent --auto-update-on-conflict 2>&1 | tee analysis_output.txt",
                            "if [ $? -ne 0 ]; then echo 'Analysis agent launch failed - see output above'; exit 1; fi",
                            "cat analysis_output.txt",
                            "ANALYSIS_ARN=$(grep -o 'arn:aws:bedrock-agentcore:[^:]*:[^:]*:runtime/[^[:space:]]*' analysis_output.txt | head -1)",
                            "echo \"Analysis ARN: $ANALYSIS_ARN\"",
                            "if [ ! -z \"$ANALYSIS_ARN\" ]; then aws ssm put-parameter --name '/quality-inspection/agentcore-runtime/analysis' --value \"$ANALYSIS_ARN\" --type String --overwrite; else echo 'No Analysis ARN found, skipping SSM parameter'; fi",
                            "echo 'Deploying sop agent'",
                            "agentcore launch --agent sop_agent --auto-update-on-conflict 2>&1 | tee sop_output.txt",
                            "if [ $? -ne 0 ]; then echo 'SOP agent launch failed - see output above'; exit 1; fi",
                            "cat sop_output.txt",
                            "SOP_ARN=$(grep -o 'arn:aws:bedrock-agentcore:[^:]*:[^:]*:runtime/[^[:space:]]*' sop_output.txt | head -1)",
                            "echo \"SOP ARN: $SOP_ARN\"",
                            "if [ ! -z \"$SOP_ARN\" ]; then aws ssm put-parameter --name '/quality-inspection/agentcore-runtime/sop' --value \"$SOP_ARN\" --type String --overwrite; else echo 'No SOP ARN found, skipping SSM parameter'; fi",
                            "echo 'Deploying action agent'",
                            "agentcore launch --agent action_agent --auto-update-on-conflict 2>&1 | tee action_output.txt",
                            "if [ $? -ne 0 ]; then echo 'Action agent launch failed - see output above'; exit 1; fi",
                            "cat action_output.txt",
                            "ACTION_ARN=$(grep -o 'arn:aws:bedrock-agentcore:[^:]*:[^:]*:runtime/[^[:space:]]*' action_output.txt | head -1)",
                            "echo \"Action ARN: $ACTION_ARN\"",
                            "if [ ! -z \"$ACTION_ARN\" ]; then aws ssm put-parameter --name '/quality-inspection/agentcore-runtime/action' --value \"$ACTION_ARN\" --type String --overwrite; else echo 'No Action ARN found, skipping SSM parameter'; fi",
                            "echo 'Deploying communication agent'",
                            "agentcore launch --agent communication_agent --auto-update-on-conflict 2>&1 | tee communication_output.txt",
                            "if [ $? -ne 0 ]; then echo 'Communication agent launch failed - see output above'; exit 1; fi",
                            "cat communication_output.txt",
                            "COMMUNICATION_ARN=$(grep -o 'arn:aws:bedrock-agentcore:[^:]*:[^:]*:runtime/[^[:space:]]*' communication_output.txt | head -1)",
                            "echo \"Communication ARN: $COMMUNICATION_ARN\"",
                            "if [ ! -z \"$COMMUNICATION_ARN\" ]; then aws ssm put-parameter --name '/quality-inspection/agentcore-runtime/communication' --value \"$COMMUNICATION_ARN\" --type String --overwrite; else echo 'No Communication ARN found, skipping SSM parameter'; fi",
                            "echo 'AgentCore deployment completed'",
                            "echo 'Runtime ARNs saved to SSM parameters'"
                        ]
                    },
                    "post_build": {
                        "commands": [
                            "echo 'Build completed - checking for any errors:'",
                            "if [ -f orchestrator_output.txt ]; then echo 'Orchestrator output:' && cat orchestrator_output.txt; fi",
                            "if [ -f vision_output.txt ]; then echo 'Vision output:' && cat vision_output.txt; fi"
                        ]
                    }
                }
            }),
            source=codebuild.Source.s3(
                bucket=self.bucket,
                path="repo"
            )
        )
        
        # Output the CodeBuild project name with dynamic naming pattern
        CfnOutput(self, "QualityInspectionAgentCoreDeploymentProject", value=project.project_name)
        CfnOutput(self, "AgentCoreCodeBuildRoleArn", value=agentcore_codebuild_role.role_arn)
        
        return project
    
    def deploy_custom_ui(self):
        """Deploy Streamlit UI to Fargate (if shared resources available)"""
        # Check if required shared resources are available
        if not self.shared_resources or not self.shared_resources.get('vpc'):
            print("Skipping custom UI deployment - no VPC in shared resources")
            return
        
        # Import custom UI construct
        import sys
        import os
        cdk_root = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'cdk')
        sys.path.insert(0, cdk_root)
        
        try:
            from stacks.constructs.custom_ui import CustomUIConstruct
            
            # Get agent path
            agent_path = os.path.dirname(os.path.dirname(__file__))
            
            # Deploy custom UI
            self.custom_ui = CustomUIConstruct(
                self, "CustomUI",
                agent_name="quality-inspection",
                agent_path=agent_path,
                ui_config={
                    "type": "streamlit",
                    "path": "/quality-inspection",
                    "port": 8501
                },
                vpc=self.shared_resources.get('vpc'),
                cluster=self.shared_resources.get('ecs_cluster'),
                listener=self.shared_resources.get('alb_listener'),
                shared_resources=self.shared_resources,
                auth_user=self.shared_resources.get('auth_user', 'admin'),
                auth_password=self.shared_resources.get('auth_password', 'changeme')
            )
            
            print("Custom UI deployed successfully")
        except Exception as e:
            print(f"Failed to deploy custom UI: {e}")
        finally:
            sys.path.pop(0)
    


    
