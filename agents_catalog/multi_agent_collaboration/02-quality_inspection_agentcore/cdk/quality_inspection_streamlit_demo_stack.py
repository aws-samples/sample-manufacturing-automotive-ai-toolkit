from aws_cdk import (
    Stack,
    Duration,
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_logs as logs,
    aws_ecr_assets as ecr_assets,
    aws_elasticloadbalancingv2 as elbv2,
    aws_certificatemanager as acm,
    CfnOutput,
    RemovalPolicy
)
from constructs import Construct

class QualityInspectionStreamlitDemoStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Import VPC from main stack
        self.vpc = ec2.Vpc.from_lookup(
            self, "ImportedVpc",
            vpc_name="vpc-agentic-quality-inspection"
        )
        
        # Create ECS cluster
        self.cluster = self.create_ecs_cluster()
        
        # Create ALB and Streamlit service
        self.alb, self.streamlit_service = self.create_streamlit_service_with_alb()
        
        # Output service information
        CfnOutput(
            self, "StreamlitServiceName",
            value=self.streamlit_service.service_name,
            description="ECS Service name for Streamlit app"
        )
        
        CfnOutput(
            self, "StreamlitURL",
            value="https://qualityinspection.grantaws.people.aws.dev",
            description="HTTPS URL for Streamlit app"
        )
    
    def create_ecs_cluster(self):
        """Create ECS cluster for Streamlit app"""
        cluster = ecs.Cluster(
            self, "StreamlitCluster",
            cluster_name="quality-inspection-streamlit",
            vpc=self.vpc,
            enable_fargate_capacity_providers=True
        )
        
        return cluster
    
    def create_streamlit_service_with_alb(self):
        """Create ALB and ECS Fargate service for Streamlit app"""
        
        # Create task execution role
        task_execution_role = iam.Role(
            self, "StreamlitTaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
            ]
        )
        
        # Create task role with application permissions
        task_role = iam.Role(
            self, "StreamlitTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            inline_policies={
                "StreamlitAppPermissions": iam.PolicyDocument(
                    statements=[
                        # S3 access for images
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:ListBucket"
                            ],
                            resources=[
                                f"arn:aws:s3:::machinepartimages-{self.account}",
                                f"arn:aws:s3:::machinepartimages-{self.account}/*"
                            ]
                        ),
                        # DynamoDB access
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "dynamodb:GetItem",
                                "dynamodb:Scan",
                                "dynamodb:Query"
                            ],
                            resources=[
                                f"arn:aws:dynamodb:{self.region}:{self.account}:table/vision-inspection-data",
                                f"arn:aws:dynamodb:{self.region}:{self.account}:table/sop-decisions",
                                f"arn:aws:dynamodb:{self.region}:{self.account}:table/action-execution-log",
                                f"arn:aws:dynamodb:{self.region}:{self.account}:table/erp-integration-log",
                                f"arn:aws:dynamodb:{self.region}:{self.account}:table/historical-trends"
                            ]
                        ),
                        # AgentCore invocation
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "bedrock-agentcore:InvokeAgentRuntime"
                            ],
                            resources=[
                                f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:runtime/*"
                            ]
                        )
                    ]
                )
            }
        )
        
        # Create Docker image asset
        streamlit_image = ecr_assets.DockerImageAsset(
            self, "StreamlitImage",
            directory="../src/demo_app",
            platform=ecr_assets.Platform.LINUX_AMD64
        )
        
        # Create log group
        log_group = logs.LogGroup(
            self, "StreamlitLogGroup",
            log_group_name="/ecs/quality-inspection-streamlit",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK
        )
        
        # Create task definition
        task_definition = ecs.FargateTaskDefinition(
            self, "StreamlitTaskDefinition",
            memory_limit_mib=2048,
            cpu=1024,
            execution_role=task_execution_role,
            task_role=task_role,
            family="quality-inspection-streamlit"
        )
        
        # Add container
        container = task_definition.add_container(
            "StreamlitContainer",
            image=ecs.ContainerImage.from_docker_image_asset(streamlit_image),
            port_mappings=[
                ecs.PortMapping(
                    container_port=8501,
                    protocol=ecs.Protocol.TCP
                )
            ],
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="streamlit",
                log_group=log_group
            ),
            environment={
                "AWS_DEFAULT_REGION": self.region
            }
        )
        
        # Create security group
        security_group = ec2.SecurityGroup(
            self, "StreamlitSecurityGroup",
            vpc=self.vpc,
            description="Security group for Streamlit ECS service",
            allow_all_outbound=True
        )
        
        # Allow inbound traffic on port 8501 from VPC
        security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(8501),
            description="Streamlit port from VPC"
        )
        
        # Create ECS service
        service = ecs.FargateService(
            self, "StreamlitService",
            cluster=self.cluster,
            task_definition=task_definition,
            desired_count=1,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[security_group],
            service_name="quality-inspection-streamlit"
        )
        
        # Create ALB
        alb = elbv2.ApplicationLoadBalancer(
            self, "StreamlitALB",
            vpc=self.vpc,
            internet_facing=True,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC
            )
        )
        
        # Create ACM certificate for subdomain
        certificate = acm.Certificate(
            self, "StreamlitCertificate",
            domain_name="qualityinspection.grantaws.people.aws.dev",
            validation=acm.CertificateValidation.from_dns()
        )
        
        # Create target group
        target_group = elbv2.ApplicationTargetGroup(
            self, "StreamlitTargetGroup",
            vpc=self.vpc,
            port=8501,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(
                enabled=True,
                healthy_http_codes="200",
                path="/_stcore/health",
                protocol=elbv2.Protocol.HTTP
            )
        )
        
        # Add HTTPS listener
        https_listener = alb.add_listener(
            "StreamlitHTTPSListener",
            port=443,
            protocol=elbv2.ApplicationProtocol.HTTPS,
            certificates=[certificate],
            default_target_groups=[target_group]
        )
        
        # Add HTTP listener with redirect to HTTPS
        alb.add_listener(
            "StreamlitHTTPListener",
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            default_action=elbv2.ListenerAction.redirect(
                protocol="HTTPS",
                port="443",
                permanent=True
            )
        )
        
        # Update security group to allow ALB traffic
        security_group.add_ingress_rule(
            peer=ec2.Peer.security_group_id(alb.connections.security_groups[0].security_group_id),
            connection=ec2.Port.tcp(8501),
            description="ALB to Streamlit"
        )
        
        # Add ALB security group rules
        alb.connections.allow_from_any_ipv4(
            ec2.Port.tcp(443),
            "HTTPS from anywhere"
        )
        alb.connections.allow_from_any_ipv4(
            ec2.Port.tcp(80),
            "HTTP redirect to HTTPS"
        )
        
        # Attach service to target group after ALB is fully configured
        service.attach_to_application_target_group(target_group)
        
        # Ensure proper dependency ordering
        target_group.node.add_dependency(alb)
        service.node.add_dependency(target_group)
        
        return alb, service
