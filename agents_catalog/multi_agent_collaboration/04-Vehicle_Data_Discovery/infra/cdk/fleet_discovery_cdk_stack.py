#!/usr/bin/env python3
"""
Fleet Discovery Studio - Foundational Infrastructure (CDK)
Production-grade EC2-backed ECS cluster with proper scaling and security
"""

from aws_cdk import (
    Stack,
    NestedStack,
    Duration,
    RemovalPolicy,
    CustomResource,
    Aspects,
    Tags,
    aws_s3 as s3,
    aws_iam as iam,
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_logs as logs,
    aws_autoscaling as autoscaling,
    aws_servicediscovery as servicediscovery,
    aws_lambda as lambda_,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_sns as sns,
    aws_sqs as sqs,
    aws_s3_notifications as s3n,
    aws_cognito as cognito,
    aws_codebuild as codebuild,
    aws_ecr as ecr,
    aws_apprunner as apprunner,
    custom_resources as cr,
    aws_s3_deployment as s3deploy,
    CfnOutput,
)
from constructs import Construct
from cdk_nag import NagSuppressions
import os
import hashlib

class FleetDiscoveryCdkStack(NestedStack):

    def __init__(self, scope: Construct, construct_id: str, shared_resources: dict = None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Resource tagging strategy
        # Exclude App Runner CfnService — tag changes force replacement, which
        # fails when service_name is set because the old service still exists.
        Tags.of(self).add("Application", "fleet-discovery",
                          exclude_resource_types=["AWS::AppRunner::Service"])
        Tags.of(self).add("ManagedBy", "cdk",
                          exclude_resource_types=["AWS::AppRunner::Service"])

        # Generate unique_id from stack name for consistent naming
        unique_id = hashlib.md5(construct_id.encode(), usedforsecurity=False).hexdigest()[:8]

        # ECR REPOSITORIES for pipeline images
        self.ecr_repo = ecr.Repository(
            self, "FleetPipelineRepo",
            repository_name=f"vehicle-fleet-pipeline-{unique_id}",
            removal_policy=RemovalPolicy.DESTROY,
            empty_on_delete=True,
        )

        # Image URIs from ECR (built by CodeBuild)
        arm64_image_uri = f"{self.ecr_repo.repository_uri}:arm64-latest"
        gpu_image_uri = f"{self.ecr_repo.repository_uri}:gpu-amd64-latest"
        phase6_image_uri = f"{self.ecr_repo.repository_uri}:arm64-latest"

        # VPC - Dedicated network for Fleet Discovery Studio
        self.vpc = ec2.Vpc(
            self, "FleetDiscoveryVPC",
            vpc_name="fleet-discovery-vpc",
            availability_zones=["us-west-2c", "us-west-2d"],
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="fleet-public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="fleet-private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24
                )
            ],
            flow_logs={"FlowLog": ec2.FlowLogOptions(destination=ec2.FlowLogDestination.to_cloud_watch_logs())}
        )

        # ECS CLUSTER with Container Insights enabled
        self.ecs_cluster = ecs.Cluster(
            self, "FleetCPUCluster",
            cluster_name=f"fleet-cpu-cluster-{unique_id}",
            vpc=self.vpc,
            container_insights=True
        )

        # IAM ROLE for ECS instances - Scoped permissions for fleet discovery pipeline
        self.ecs_instance_role = iam.Role(
            self, "FleetECSInstanceRole",
            role_name=f"fleet-ecs-instance-role-{unique_id}",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonEC2ContainerServiceforEC2Role"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"),
            ]
        )

        # CREATE SECURITY GROUP FIRST (needed by launch template)
        self.ecs_security_group = self._create_ecs_security_group()

        # LAUNCH TEMPLATE - Modern pattern without redundant User Data
        self.launch_template = ec2.LaunchTemplate(
            self, "FleetLaunchTemplate",
            launch_template_name=f"fleet-arm64-lt-{unique_id}",
            instance_type=ec2.InstanceType("c7g.16xlarge"),
            machine_image=ecs.EcsOptimizedImage.amazon_linux2(
                hardware_type=ecs.AmiHardwareType.ARM
            ),
            security_group=self.ecs_security_group,
            role=self.ecs_instance_role,
        )

        # SNS Topic for ASG notifications
        self.asg_notification_topic = sns.Topic(
            self, "FleetASGNotificationTopic",
            topic_name=f"fleet-asg-notifications-{unique_id}",
            enforce_ssl=True
        )

        # AUTO SCALING GROUP with notifications
        self.auto_scaling_group = autoscaling.AutoScalingGroup(
            self, "FleetEC2ASG",
            auto_scaling_group_name=f"fleet-arm64-asg-{unique_id}",
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            launch_template=self.launch_template,
            min_capacity=1,
            max_capacity=5,
            health_checks=autoscaling.HealthChecks.ec2(),
            update_policy=autoscaling.UpdatePolicy.rolling_update(
                max_batch_size=1,
                min_instances_in_service=1
            ),
            notifications=[autoscaling.NotificationConfiguration(
                topic=self.asg_notification_topic,
                scaling_events=autoscaling.ScalingEvents.ALL
            )]
        )

        # GPU LAUNCH TEMPLATE for Phase 3 InternVideo2.5
        gpu_user_data = ec2.UserData.for_linux()
        gpu_user_data.add_commands(
            f"echo ECS_CLUSTER={self.ecs_cluster.cluster_name} >> /etc/ecs/ecs.config",
            "echo ECS_ENABLE_GPU_SUPPORT=true >> /etc/ecs/ecs.config"
        )

        self.gpu_launch_template = ec2.LaunchTemplate(
            self, "FleetGPULaunchTemplate",
            launch_template_name=f"fleet-gpu-lt-{unique_id}",
            machine_image=ecs.EcsOptimizedImage.amazon_linux2(
                hardware_type=ecs.AmiHardwareType.GPU
            ),
            security_group=self.ecs_security_group,
            role=self.ecs_instance_role,
            user_data=gpu_user_data,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/xvda",
                    volume=ec2.BlockDeviceVolume.ebs(
                        volume_size=500,
                        volume_type=ec2.EbsDeviceVolumeType.GP3
                    )
                )
            ]
        )

        # GPU AUTO SCALING GROUP with mixed instance types for better availability
        self.gpu_auto_scaling_group = autoscaling.AutoScalingGroup(
            self, "FleetGPUASG",
            auto_scaling_group_name=f"fleet-gpu-asg-{unique_id}",
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            mixed_instances_policy=autoscaling.MixedInstancesPolicy(
                launch_template=self.gpu_launch_template,
                launch_template_overrides=[
                    autoscaling.LaunchTemplateOverrides(instance_type=ec2.InstanceType("g5.4xlarge")),
                    autoscaling.LaunchTemplateOverrides(instance_type=ec2.InstanceType("g5.8xlarge")),
                    autoscaling.LaunchTemplateOverrides(instance_type=ec2.InstanceType("g5.2xlarge")),
                ],
                instances_distribution=autoscaling.InstancesDistribution(
                    on_demand_percentage_above_base_capacity=100,
                )
            ),
            min_capacity=1,
            max_capacity=3,
            health_checks=autoscaling.HealthChecks.ec2(),
            update_policy=autoscaling.UpdatePolicy.rolling_update(
                max_batch_size=1,
                min_instances_in_service=0
            ),
            notifications=[autoscaling.NotificationConfiguration(
                topic=self.asg_notification_topic,
                scaling_events=autoscaling.ScalingEvents.ALL
            )]
        )

        # ARM64 CAPACITY PROVIDER
        self.arm64_capacity_provider = ecs.AsgCapacityProvider(
            self, "FleetCapacityProvider",
            capacity_provider_name=f"fleet-arm64-cp-{unique_id}",
            auto_scaling_group=self.auto_scaling_group,
            enable_managed_scaling=True,
            enable_managed_termination_protection=False,
            target_capacity_percent=80,
            minimum_scaling_step_size=1,
            maximum_scaling_step_size=3
        )

        # GPU CAPACITY PROVIDER
        self.gpu_capacity_provider = ecs.AsgCapacityProvider(
            self, "FleetGPUCapacityProvider",
            capacity_provider_name=f"fleet-gpu-cp-{unique_id}",
            auto_scaling_group=self.gpu_auto_scaling_group,
            enable_managed_scaling=True,
            enable_managed_termination_protection=False,
            target_capacity_percent=80,
            minimum_scaling_step_size=1,
            maximum_scaling_step_size=3
        )

        # Add BOTH capacity providers to our cluster
        self.ecs_cluster.add_asg_capacity_provider(self.arm64_capacity_provider)
        self.ecs_cluster.add_asg_capacity_provider(self.gpu_capacity_provider)

        # Enforce SSL on lifecycle hook SNS topics created by ASG
        for asg in [self.auto_scaling_group, self.gpu_auto_scaling_group]:
            for child in asg.node.find_all():
                if isinstance(child, sns.Topic):
                    child.add_to_resource_policy(iam.PolicyStatement(
                        sid="EnforceSSL",
                        effect=iam.Effect.DENY,
                        principals=[iam.AnyPrincipal()],
                        actions=["sns:Publish"],
                        resources=[child.topic_arn],
                        conditions={"Bool": {"aws:SecureTransport": "false"}}
                    ))

        # S3 Access Logs Bucket
        self.access_logs_bucket = s3.Bucket(
            self, "FleetAccessLogsBucket",
            bucket_name=f"fleet-logs-{unique_id}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            enforce_ssl=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )

        # S3 BUCKET - Create new bucket for this deployment
        # CORS will be added after App Runner is created via custom resource
        self.discovery_bucket = s3.Bucket(
            self, "FleetDiscoveryBucket",
            bucket_name=f"fleet-discovery-{unique_id}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            enforce_ssl=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            server_access_logs_bucket=self.access_logs_bucket,
            server_access_logs_prefix="discovery-bucket/",
        )

        # S3 BUCKET - Vector storage (regular S3 for fallback)
        self.vector_bucket = s3.Bucket(
            self, "FleetVectorBucket",
            bucket_name=f"fleet-vectors-{unique_id}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            enforce_ssl=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            server_access_logs_bucket=self.access_logs_bucket,
            server_access_logs_prefix="vector-bucket/",
        )

        # S3 VECTORS - Create vector bucket and indices via Custom Resource
        s3vectors_lambda = lambda_.Function(
            self, "S3VectorsSetupLambda",
            function_name=f"fleet-s3vectors-setup-{unique_id}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            timeout=Duration.minutes(5),
            code=lambda_.Code.from_inline('''
import boto3
import cfnresponse

def handler(event, context):
    try:
        props = event['ResourceProperties']
        bucket_name = props['VectorBucketName']
        region = props['Region']
        
        s3v = boto3.client('s3vectors', region_name=region)
        
        if event['RequestType'] in ['Create', 'Update']:
            # Create vector bucket
            try:
                s3v.create_vector_bucket(vectorBucketName=bucket_name)
                print(f"Created vector bucket: {bucket_name}")
            except Exception as e:
                if 'already exists' not in str(e).lower() and 'Conflict' not in str(e):
                    raise
                print(f"Vector bucket already exists: {bucket_name}")
            
            # Create behavioral index (1536 dims for Cohere embed-v4)
            try:
                s3v.create_index(
                    vectorBucketName=bucket_name,
                    indexName='behavioral-metadata-index',
                    dimension=1536,
                    distanceMetric='cosine',
                    dataType='float32',
                    metadataConfiguration={
                        'nonFilterableMetadataKeys': [
                            'scene_id', 'behavioral_features_text', 'extraction_method',
                            'processing_timestamp', 'cohere_model_version'
                        ]
                    }
                )
                print("Created behavioral-metadata-index")
            except Exception as e:
                if 'already exists' not in str(e).lower() and 'Conflict' not in str(e):
                    print(f"Index creation error: {e}")
            
            # Create visual index (768 dims for Cosmos-Embed1)
            try:
                s3v.create_index(
                    vectorBucketName=bucket_name,
                    indexName='video-similarity-index',
                    dimension=768,
                    distanceMetric='cosine',
                    dataType='float32',
                    metadataConfiguration={
                        'nonFilterableMetadataKeys': [
                            'scene_id', 'camera_angles', 'video_metadata',
                            'processing_timestamp', 'cosmos_model_version'
                        ]
                    }
                )
                print("Created video-similarity-index")
            except Exception as e:
                if 'already exists' not in str(e).lower() and 'Conflict' not in str(e):
                    print(f"Index creation error: {e}")
            
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {'VectorBucket': bucket_name})
        
        elif event['RequestType'] == 'Delete':
            try:
                s3v.delete_index(vectorBucketName=bucket_name, indexName='behavioral-metadata-index')
            except: pass
            try:
                s3v.delete_index(vectorBucketName=bucket_name, indexName='video-similarity-index')
            except: pass
            try:
                s3v.delete_vector_bucket(vectorBucketName=bucket_name)
            except: pass
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
    except Exception as e:
        print(f"Error: {e}")
        cfnresponse.send(event, context, cfnresponse.FAILED, {'Error': str(e)})
'''),
        )
        
        s3vectors_lambda.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "s3vectors:CreateVectorBucket", "s3vectors:DeleteVectorBucket",
                "s3vectors:GetVectorBucket", "s3vectors:ListVectorBuckets",
                "s3vectors:CreateIndex", "s3vectors:DeleteIndex",
                "s3vectors:GetIndex", "s3vectors:ListIndexes",
            ],
            resources=[f"arn:aws:s3vectors:{Stack.of(self).region}:{Stack.of(self).account}:*"]
        ))

        self.s3vectors_setup = CustomResource(
            self, "S3VectorsSetup",
            service_token=s3vectors_lambda.function_arn,
            properties={
                "VectorBucketName": f"fleet-vectors-{unique_id}",
                "Region": Stack.of(self).region
            }
        )

        # CLOUDWATCH LOG GROUP
        self.log_group = logs.LogGroup(
            self, "FleetLogGroup",
            log_group_name=f"/aws/fleet-discovery-{unique_id}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY
        )

        # IAM ROLES - Properly scoped permissions (NO wildcards)

        # ECS Task Execution Role
        self.ecs_task_execution_role = iam.Role(
            self, "FleetECSTaskExecutionRole",
            role_name=f"fleet-ecs-execution-role-{unique_id}",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
            ]
        )

        # ECS Task Role - Scoped permissions for fleet discovery pipeline
        self.ecs_task_role = iam.Role(
            self, "FleetECSTaskRole",
            role_name=f"fleet-ecs-task-role-{unique_id}",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonBedrockFullAccess")
            ]
        )

        # S3 permissions for pipeline data
        self.ecs_task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:DeleteObject"],
                resources=["arn:aws:s3:::fleet-*", "arn:aws:s3:::fleet-*/*"]
            )
        )

        # Step Functions permissions (full access for task callbacks)
        self.ecs_task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["states:*"],
                resources=["arn:aws:states:*:*:stateMachine:fleet-*", "arn:aws:states:*:*:execution:fleet-*:*"]
            )
        )

        # CloudWatch Logs permissions
        self.ecs_task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                resources=["arn:aws:logs:*:*:log-group:/aws/fleet-*", "arn:aws:logs:*:*:log-group:/aws/fleet-*:*"]
            )
        )

        # ECR permissions
        self.ecs_task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ecr:GetAuthorizationToken", "ecr:BatchCheckLayerAvailability", "ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage"],
                resources=["*"]
            )
        )

        # S3 Vectors permissions
        self.ecs_task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3vectors:PutVectors", "s3vectors:GetVectors",
                    "s3vectors:DeleteVectors", "s3vectors:QueryVectors",
                    "s3vectors:ListVectors", "s3vectors:GetIndex",
                    "s3vectors:ListIndexes", "s3vectors:GetVectorBucket",
                ],
                resources=[f"arn:aws:s3vectors:{Stack.of(self).region}:{Stack.of(self).account}:*"]
            )
        )

        # Add explicit AgentCore permissions (for Phase 6 orchestrator)
        self.ecs_task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:InvokeAgentRuntime"
                ],
                resources=["*"]
            )
        )

        # Add explicit Cohere Bedrock model permissions (for Phase 4-5 embedding migration)
        self.ecs_task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                resources=[
                    "arn:aws:bedrock:*::foundation-model/cohere.embed-v4:0",
                    "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v2:0",
                    f"arn:aws:bedrock:{Stack.of(self).region}:{Stack.of(self).account}:inference-profile/us.cohere.embed-v4:0",
                    f"arn:aws:bedrock:{Stack.of(self).region}:{Stack.of(self).account}:inference-profile/us.amazon.titan-embed-text-v2:0",
                ]
            )
        )

        # AGENTCORE INTEGRATION - 3-Agent HIL System deployed to AgentCore runtime (no ECS services needed)
        # HIL Agent mapping with "body snatching" approach (NEW DEPLOYED VERSIONS):
        # - behavioral_gap_analysis_agent-W8F8B7DuQb → Scene Understanding Agent
        # - safety_validation_agent-5mBQ4FGj2E → Anomaly Detection Agent
        # - intelligence_gathering_agent-D2agaCFcUo → Similarity Search Agent
        # - fleet_optimization_agent → REMOVED (functionality distributed)

        # CLOUDFORMATION OUTPUTS
        CfnOutput(self, "VPCId",
            value=self.vpc.vpc_id,
            description="Fleet Discovery Studio VPC ID"
        )

        CfnOutput(self, "ECSClusterName",
            value=self.ecs_cluster.cluster_name,
            description="Fleet GPU ECS Cluster (EC2-backed with managed scaling)"
        )

        CfnOutput(self, "ECSClusterArn",
            value=self.ecs_cluster.cluster_arn,
            description="Fleet ECS Cluster ARN"
        )

        CfnOutput(self, "ARM64AutoScalingGroupName",
            value=self.auto_scaling_group.auto_scaling_group_name,
            description="Fleet ARM64 Auto Scaling Group (ECS-managed)"
        )

        CfnOutput(self, "GPUAutoScalingGroupName",
            value=self.gpu_auto_scaling_group.auto_scaling_group_name,
            description="Fleet GPU Auto Scaling Group (ECS-managed)"
        )

        CfnOutput(self, "ARM64CapacityProviderName",
            value=self.arm64_capacity_provider.capacity_provider_name,
            description="Fleet ARM64 ECS Capacity Provider (c7g.16xlarge)"
        )

        CfnOutput(self, "GPUCapacityProviderName",
            value=self.gpu_capacity_provider.capacity_provider_name,
            description="Fleet GPU ECS Capacity Provider (g5.2xlarge/g5.4xlarge/g4dn.4xlarge)"
        )

        CfnOutput(self, "S3BucketName",
            value=self.discovery_bucket.bucket_name,
            description="Fleet Discovery Studio S3 Bucket"
        )

        CfnOutput(self, "VectorBucketName",
            value=self.vector_bucket.bucket_name,
            description="Fleet Discovery Vector Storage Bucket"
        )

        CfnOutput(self, "PrivateSubnetIds",
            value=",".join([subnet.subnet_id for subnet in self.vpc.private_subnets]),
            description="Private subnet IDs for secure ECS services"
        )

        CfnOutput(self, "ECSTaskExecutionRoleArn",
            value=self.ecs_task_execution_role.role_arn,
            description="ECS Task Execution Role ARN"
        )

        CfnOutput(self, "ECSTaskRoleArn",
            value=self.ecs_task_role.role_arn,
            description="ECS Task Role ARN (scoped permissions)"
        )

        # SSM Parameters for ECS task configuration
        from aws_cdk import aws_ssm as ssm
        
        self.ssm_s3_bucket = ssm.StringParameter(
            self, "FleetS3BucketParam",
            parameter_name=f"/fleet/{unique_id}/s3-bucket",
            string_value=self.discovery_bucket.bucket_name
        )
        self.ssm_vector_bucket = ssm.StringParameter(
            self, "FleetVectorBucketParam",
            parameter_name=f"/fleet/{unique_id}/vector-bucket",
            string_value=self.vector_bucket.bucket_name
        )
        self.ssm_region = ssm.StringParameter(
            self, "FleetRegionParam",
            parameter_name=f"/fleet/{unique_id}/region",
            string_value=self.region
        )
        
        # SSM Parameters for AgentCore ARNs (populated automatically by build_launch_agentcore.py)
        # Uses fixed prefix "/fleet/vehicle-data-discovery" for predictable manifest mapping
        ssm_prefix = "/fleet/vehicle-data-discovery/agent-arns"
        self.ssm_scene_understanding_arn = ssm.StringParameter(
            self, "FleetSceneUnderstandingArnParam",
            parameter_name=f"{ssm_prefix}/scene-understanding",
            string_value="PLACEHOLDER_UPDATE_AFTER_AGENT_DEPLOYMENT"
        )
        self.ssm_anomaly_detection_arn = ssm.StringParameter(
            self, "FleetAnomalyDetectionArnParam",
            parameter_name=f"{ssm_prefix}/anomaly-detection",
            string_value="PLACEHOLDER_UPDATE_AFTER_AGENT_DEPLOYMENT"
        )
        self.ssm_similarity_search_arn = ssm.StringParameter(
            self, "FleetSimilaritySearchArnParam",
            parameter_name=f"{ssm_prefix}/similarity-search",
            string_value="PLACEHOLDER_UPDATE_AFTER_AGENT_DEPLOYMENT"
        )

        # Grant ECS task execution role access to SSM parameters
        self.ssm_s3_bucket.grant_read(self.ecs_task_execution_role)
        self.ssm_vector_bucket.grant_read(self.ecs_task_execution_role)
        self.ssm_region.grant_read(self.ecs_task_execution_role)
        self.ssm_scene_understanding_arn.grant_read(self.ecs_task_execution_role)
        self.ssm_anomaly_detection_arn.grant_read(self.ecs_task_execution_role)
        self.ssm_similarity_search_arn.grant_read(self.ecs_task_execution_role)

        # PIPELINE PHASE TASK DEFINITIONS - BRIDGE networking for ephemeral tasks

        # Phase 1: Multi-sensor ROS bag extraction
        self.phase1_task_def = ecs.Ec2TaskDefinition(
            self, "FleetPhase1TaskDef",
            family="fleet-phase1-extraction",
            execution_role=self.ecs_task_execution_role,
            task_role=self.ecs_task_role,
            network_mode=ecs.NetworkMode.BRIDGE,
            placement_constraints=[
                ecs.PlacementConstraint.member_of("attribute:ecs.instance-type =~ c7g.*")
            ]
        )

        self.phase1_task_def.add_container(
            "phase1-container",
            image=ecs.ContainerImage.from_registry(arm64_image_uri),
            command=["python3", "/app/phase-1/multi_sensor_rosbag_extractor.py"],
            memory_limit_mib=4096,
            cpu=2048,
            secrets={
                "AWS_DEFAULT_REGION": ecs.Secret.from_ssm_parameter(self.ssm_region),
                "S3_BUCKET": ecs.Secret.from_ssm_parameter(self.ssm_s3_bucket)
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="fleet-phase1-extraction",
                log_group=self.log_group
            )
        )

        # Phase 2: Video reconstruction
        self.phase2_task_def = ecs.Ec2TaskDefinition(
            self, "FleetPhase2TaskDef",
            family="fleet-phase2-video",
            execution_role=self.ecs_task_execution_role,
            task_role=self.ecs_task_role,
            network_mode=ecs.NetworkMode.BRIDGE,
            placement_constraints=[
                ecs.PlacementConstraint.member_of("attribute:ecs.instance-type =~ c7g.*")
            ]
        )

        self.phase2_task_def.add_container(
            "phase2-container",
            image=ecs.ContainerImage.from_registry(arm64_image_uri),
            command=["python3", "/app/phase-2/rosbag_video_reconstructor.py"],
            memory_limit_mib=8192,
            cpu=4096,
            secrets={
                "AWS_DEFAULT_REGION": ecs.Secret.from_ssm_parameter(self.ssm_region),
                "S3_BUCKET": ecs.Secret.from_ssm_parameter(self.ssm_s3_bucket)
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="fleet-phase2-video",
                log_group=self.log_group
            )
        )

        # SSM parameters for Phase 3 specific config
        self.ssm_bedrock_model = ssm.StringParameter(
            self, "FleetBedrockModelParam",
            parameter_name=f"/fleet/{unique_id}/bedrock-model",
            string_value="us.anthropic.claude-sonnet-4-20250514-v1:0"
        )
        self.ssm_vector_index = ssm.StringParameter(
            self, "FleetVectorIndexParam",
            parameter_name=f"/fleet/{unique_id}/vector-index",
            string_value="behavioral-metadata-index"
        )
        self.ssm_bedrock_model.grant_read(self.ecs_task_execution_role)
        self.ssm_vector_index.grant_read(self.ecs_task_execution_role)

        # Phase 3: InternVideo2.5 behavioral analysis (GPU-targeted)
        self.phase3_task_def = ecs.Ec2TaskDefinition(
            self, "FleetPhase3TaskDef",
            family="fleet-phase3-internvideo25-gpu",
            execution_role=self.ecs_task_execution_role,
            task_role=self.ecs_task_role,
            network_mode=ecs.NetworkMode.BRIDGE,
            placement_constraints=[
                ecs.PlacementConstraint.member_of("attribute:ecs.instance-type =~ g5.* or attribute:ecs.instance-type =~ g4dn.*")
            ]
        )

        self.phase3_task_def.add_container(
            "phase3-container",
            image=ecs.ContainerImage.from_registry(gpu_image_uri),
            command=["python3", "/app/internvideo25_behavioral_analyzer.py"],
            memory_limit_mib=61440,
            cpu=1024,
            gpu_count=1,
            secrets={
                "AWS_DEFAULT_REGION": ecs.Secret.from_ssm_parameter(self.ssm_region),
                "S3_BUCKET": ecs.Secret.from_ssm_parameter(self.ssm_s3_bucket),
                "BEDROCK_MODEL_ID": ecs.Secret.from_ssm_parameter(self.ssm_bedrock_model),
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="fleet-phase3-internvideo25",
                log_group=self.log_group
            )
        )

        # Phase 4-5: S3 Vectors embeddings
        self.phase45_task_def = ecs.Ec2TaskDefinition(
            self, "FleetPhase45TaskDef",
            family="fleet-phase45-embeddings",
            execution_role=self.ecs_task_execution_role,
            task_role=self.ecs_task_role,
            network_mode=ecs.NetworkMode.BRIDGE,
            placement_constraints=[
                ecs.PlacementConstraint.member_of("attribute:ecs.instance-type =~ c7g.*")
            ]
        )

        self.phase45_task_def.add_container(
            "phase45-container",
            image=ecs.ContainerImage.from_registry(arm64_image_uri),
            command=["python3", "/app/phase-4-5/s3_vectors_behavioral_embeddings.py"],
            memory_limit_mib=2048,
            cpu=1024,
            secrets={
                "AWS_DEFAULT_REGION": ecs.Secret.from_ssm_parameter(self.ssm_region),
                "S3_BUCKET": ecs.Secret.from_ssm_parameter(self.ssm_s3_bucket),
                "VECTOR_BUCKET_NAME": ecs.Secret.from_ssm_parameter(self.ssm_vector_bucket),
                "VECTOR_INDEX_NAME": ecs.Secret.from_ssm_parameter(self.ssm_vector_index),
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="fleet-phase45-embeddings",
                log_group=self.log_group
            )
        )

        # Phase 6: Enhanced Multi-agent orchestrator
        self.phase6_task_def = ecs.Ec2TaskDefinition(
            self, "FleetPhase6TaskDef",
            family="fleet-phase6-orchestrator",
            execution_role=self.ecs_task_execution_role,
            task_role=self.ecs_task_role,
            network_mode=ecs.NetworkMode.BRIDGE,
            placement_constraints=[
                ecs.PlacementConstraint.member_of("attribute:ecs.instance-type =~ c7g.*")
            ]
        )

        self.phase6_task_def.add_container(
            "phase6-container",
            image=ecs.ContainerImage.from_registry(phase6_image_uri),
            command=["python3", "/app/phase-6/microservice_orchestrator.py"],
            memory_limit_mib=2048,
            cpu=1024,
            secrets={
                "AWS_DEFAULT_REGION": ecs.Secret.from_ssm_parameter(self.ssm_region),
                "S3_BUCKET": ecs.Secret.from_ssm_parameter(self.ssm_s3_bucket),
                "VECTOR_BUCKET_NAME": ecs.Secret.from_ssm_parameter(self.ssm_vector_bucket),
                "VECTOR_INDEX_NAME": ecs.Secret.from_ssm_parameter(self.ssm_vector_index),
                "SCENE_UNDERSTANDING_AGENT_ARN": ecs.Secret.from_ssm_parameter(self.ssm_scene_understanding_arn),
                "ANOMALY_DETECTION_AGENT_ARN": ecs.Secret.from_ssm_parameter(self.ssm_anomaly_detection_arn),
                "SIMILARITY_SEARCH_AGENT_ARN": ecs.Secret.from_ssm_parameter(self.ssm_similarity_search_arn),
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="fleet-phase6-enhanced-orchestrator",
                log_group=self.log_group
            )
        )

        # ALERTING INFRASTRUCTURE

        # SNS Topics for notifications with SSL enforcement
        self.success_topic = sns.Topic(
            self, "FleetSuccessTopic",
            topic_name="fleet-pipeline-success",
            display_name="Fleet Pipeline Success Notifications",
            enforce_ssl=True
        )

        self.failure_topic = sns.Topic(
            self, "FleetFailureTopic",
            topic_name="fleet-critical-failures",
            display_name="Fleet Critical Failure Alerts",
            enforce_ssl=True
        )

        # Final DLQ for unprocessable messages
        self.final_dlq = sqs.Queue(
            self, "FleetFinalDLQ",
            queue_name="fleet-final-dlq",
            retention_period=Duration.days(14),
            enforce_ssl=True
        )

        # SQS DLQ for failed scenes
        self.failed_scenes_dlq = sqs.Queue(
            self, "FleetFailedScenesDLQ",
            queue_name="fleet-failed-scenes-dlq",
            visibility_timeout=Duration.minutes(5),
            retention_period=Duration.days(14),
            receive_message_wait_time=Duration.seconds(20),
            enforce_ssl=True,
            dead_letter_queue=sqs.DeadLetterQueue(queue=self.final_dlq, max_receive_count=3)
        )

        # LAMBDA FUNCTIONS

        # S3 Trigger Lambda
        self.s3_trigger_lambda = lambda_.Function(
            self, "FleetS3TriggerLambda",
            function_name=f"fleet-s3-trigger-{self.region}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.lambda_handler",
            code=lambda_.Code.from_inline(self._get_s3_trigger_lambda_code()),
            environment={
                "S3_BUCKET": self.discovery_bucket.bucket_name
            },
            timeout=Duration.seconds(30),
            memory_size=256,
            log_retention=logs.RetentionDays.ONE_WEEK
        )

        # Grant Lambda permissions
        self.discovery_bucket.grant_read(self.s3_trigger_lambda)

        # STEP FUNCTIONS STATE MACHINE - Simplified workflow (AgentCore integration)
        # Note: Agent endpoints step REMOVED - Phase 6 reads ARNs from SSM parameters

        # Step 1: Phase 1 - Multi-sensor extraction
        phase1_task = tasks.EcsRunTask(
            self, "Phase1Task",
            integration_pattern=sfn.IntegrationPattern.WAIT_FOR_TASK_TOKEN,
            cluster=self.ecs_cluster,
            task_definition=self.phase1_task_def,
            launch_target=tasks.EcsEc2LaunchTarget(),
            container_overrides=[
                tasks.ContainerOverride(
                    container_definition=self.phase1_task_def.default_container,
                    environment=[
                        tasks.TaskEnvironmentVariable(name="STEP_FUNCTIONS_TASK_TOKEN", value=sfn.JsonPath.task_token),
                        tasks.TaskEnvironmentVariable(name="SCENE_ID", value=sfn.JsonPath.string_at("$.scene_id")),
                        tasks.TaskEnvironmentVariable(name="INPUT_S3_KEY", value=sfn.JsonPath.string_at("$.input_rosbag_key")),
                        tasks.TaskEnvironmentVariable(name="OUTPUT_S3_KEY", value=sfn.JsonPath.format("processed/phase1/{}/extraction_output.json", sfn.JsonPath.string_at("$.scene_id")))
                    ]
                )
            ],
            result_path="$.phase1_raw_result"
        )
        phase1_task.add_retry(
            errors=["ECS.AmazonECSException"],
            interval=Duration.seconds(30),
            max_attempts=10,
            backoff_rate=2.0
        )

        # Parse Phase 1 result - Simplified (no agent endpoints needed)
        parse_phase1_result = sfn.Pass(
            self, "ParsePhase1Result",
            parameters={
                "scene_id.$": "$.scene_id",
                "input_rosbag_key.$": "$.input_rosbag_key",
                "phase1_result.$": "$.phase1_raw_result"
            }
        )

        # Step 3: Phase 2 - Video reconstruction
        phase2_task = tasks.EcsRunTask(
            self, "Phase2Task",
            integration_pattern=sfn.IntegrationPattern.WAIT_FOR_TASK_TOKEN,
            cluster=self.ecs_cluster,
            task_definition=self.phase2_task_def,
            launch_target=tasks.EcsEc2LaunchTarget(),
            container_overrides=[
                tasks.ContainerOverride(
                    container_definition=self.phase2_task_def.default_container,
                    environment=[
                        tasks.TaskEnvironmentVariable(name="STEP_FUNCTIONS_TASK_TOKEN", value=sfn.JsonPath.task_token),
                        tasks.TaskEnvironmentVariable(name="SCENE_ID", value=sfn.JsonPath.string_at("$.scene_id")),
                        tasks.TaskEnvironmentVariable(name="INPUT_S3_KEY", value=sfn.JsonPath.string_at("$.phase1_result.output_s3_key")),
                        tasks.TaskEnvironmentVariable(name="INPUT_ROSBAG_KEY", value=sfn.JsonPath.string_at("$.input_rosbag_key")),
                        tasks.TaskEnvironmentVariable(name="OUTPUT_S3_KEY", value=sfn.JsonPath.format("processed/phase2/{}/video_output.json", sfn.JsonPath.string_at("$.scene_id")))
                    ]
                )
            ],
            result_path="$.phase2_raw_result"
        )
        phase2_task.add_retry(
            errors=["ECS.AmazonECSException"],
            interval=Duration.seconds(30),
            max_attempts=10,
            backoff_rate=2.0
        )

        # Parse Phase 2 result
        parse_phase2_result = sfn.Pass(
            self, "ParsePhase2Result",
            parameters={
                "scene_id.$": "$.scene_id",
                "phase1_result.$": "$.phase1_result",
                "phase2_result.$": "$.phase2_raw_result"
            }
        )

        # Step 4: Phase 3 - InternVideo2.5 analysis
        phase3_task = tasks.EcsRunTask(
            self, "Phase3Task",
            integration_pattern=sfn.IntegrationPattern.WAIT_FOR_TASK_TOKEN,
            cluster=self.ecs_cluster,
            task_definition=self.phase3_task_def,
            launch_target=tasks.EcsEc2LaunchTarget(),
            heartbeat=Duration.minutes(10),
            container_overrides=[
                tasks.ContainerOverride(
                    container_definition=self.phase3_task_def.default_container,
                    environment=[
                        tasks.TaskEnvironmentVariable(name="STEP_FUNCTIONS_TASK_TOKEN", value=sfn.JsonPath.task_token),
                        tasks.TaskEnvironmentVariable(name="SCENE_ID", value=sfn.JsonPath.string_at("$.scene_id")),
                        tasks.TaskEnvironmentVariable(name="INPUT_S3_KEY", value=sfn.JsonPath.string_at("$.phase2_result.output_s3_key")),
                        tasks.TaskEnvironmentVariable(name="OUTPUT_S3_KEY", value=sfn.JsonPath.format("processed/phase3/{}/internvideo25_analysis.json", sfn.JsonPath.string_at("$.scene_id"))),
                        # FIX: Include InternVideo2.5 configuration parameters
                        tasks.TaskEnvironmentVariable(name="INTERNVIDEO_NUM_FRAMES", value="32"),
                        tasks.TaskEnvironmentVariable(name="INTERNVIDEO_INPUT_SIZE", value="448")
                    ]
                )
            ],
            result_path="$.phase3_raw_result"
        )
        phase3_task.add_retry(
            errors=["ECS.AmazonECSException"],
            interval=Duration.seconds(30),
            max_attempts=10,
            backoff_rate=2.0
        )

        # Parse Phase 3 result
        parse_phase3_result = sfn.Pass(
            self, "ParsePhase3Result",
            parameters={
                "scene_id.$": "$.scene_id",
                "phase1_result.$": "$.phase1_result",
                "phase2_result.$": "$.phase2_result",
                "phase3_result.$": "$.phase3_raw_result"
            }
        )

        # Step 5: Phase 4-5 - Embeddings
        phase45_task = tasks.EcsRunTask(
            self, "Phase45Task",
            integration_pattern=sfn.IntegrationPattern.WAIT_FOR_TASK_TOKEN,
            cluster=self.ecs_cluster,
            task_definition=self.phase45_task_def,
            launch_target=tasks.EcsEc2LaunchTarget(),
            container_overrides=[
                tasks.ContainerOverride(
                    container_definition=self.phase45_task_def.default_container,
                    environment=[
                        tasks.TaskEnvironmentVariable(name="STEP_FUNCTIONS_TASK_TOKEN", value=sfn.JsonPath.task_token),
                        tasks.TaskEnvironmentVariable(name="SCENE_ID", value=sfn.JsonPath.string_at("$.scene_id")),
                        tasks.TaskEnvironmentVariable(name="INPUT_S3_KEY", value=sfn.JsonPath.string_at("$.phase3_result.output_s3_key")),
                        tasks.TaskEnvironmentVariable(name="OUTPUT_S3_KEY", value=sfn.JsonPath.format("processed/phase4-5/{}/embeddings_output.json", sfn.JsonPath.string_at("$.scene_id")))
                    ]
                )
            ],
            result_path="$.phase45_raw_result"
        )
        phase45_task.add_retry(
            errors=["ECS.AmazonECSException"],
            interval=Duration.seconds(30),
            max_attempts=10,
            backoff_rate=2.0
        )

        # Parse Phase 4-5 result
        parse_phase45_result = sfn.Pass(
            self, "ParsePhase45Result",
            parameters={
                "scene_id.$": "$.scene_id",
                "phase1_result.$": "$.phase1_result",
                "phase2_result.$": "$.phase2_result",
                "phase3_result.$": "$.phase3_result",
                "phase45_result.$": "$.phase45_raw_result"
            }
        )

        # Step 6: Enhanced Phase 6 - Multi-agent orchestrator with iterative cycles (AgentCore integration)
        phase6_task = tasks.EcsRunTask(
            self, "Phase6Task",
            integration_pattern=sfn.IntegrationPattern.WAIT_FOR_TASK_TOKEN,
            cluster=self.ecs_cluster,
            task_definition=self.phase6_task_def,
            launch_target=tasks.EcsEc2LaunchTarget(),
            container_overrides=[
                tasks.ContainerOverride(
                    container_definition=self.phase6_task_def.default_container,
                    environment=[
                        tasks.TaskEnvironmentVariable(name="STEP_FUNCTIONS_TASK_TOKEN", value=sfn.JsonPath.task_token),
                        tasks.TaskEnvironmentVariable(name="SCENE_ID", value=sfn.JsonPath.string_at("$.scene_id")),
                        tasks.TaskEnvironmentVariable(name="INPUT_S3_KEY", value=sfn.JsonPath.string_at("$.phase45_result.output_s3_key")),
                        tasks.TaskEnvironmentVariable(name="OUTPUT_S3_KEY", value=sfn.JsonPath.format("processed/phase6/{}/enhanced_orchestration_results.json", sfn.JsonPath.string_at("$.scene_id")))
                        # Note: Agent endpoint URLs REMOVED - Phase 6 reads ARNs from SSM parameters
                    ]
                )
            ],
            result_path="$.phase6_raw_result"
        )
        phase6_task.add_retry(
            errors=["ECS.AmazonECSException"],
            interval=Duration.seconds(30),
            max_attempts=10,
            backoff_rate=2.0
        )

        # Parse final result
        parse_phase6_result = sfn.Pass(
            self, "ParsePhase6Result",
            parameters={
                "scene_id.$": "$.scene_id",
                "phase6_result.$": "$.phase6_raw_result",
                "pipeline_completion_time.$": "$$.State.EnteredTime"
            }
        )

        # Success and failure notifications
        success_notification = tasks.SnsPublish(
            self, "SuccessNotification",
            topic=self.success_topic,
            message=sfn.TaskInput.from_json_path_at("$.phase6_result"),
            subject="Fleet Enhanced Pipeline Success"
        )

        failure_notification = tasks.SnsPublish(
            self, "FailureNotification",
            topic=self.failure_topic,
            message=sfn.TaskInput.from_json_path_at("$.Error"),
            subject="Fleet Enhanced Pipeline Failure"
        )

        # Add error handling to critical tasks
        phase1_task.add_catch(
            failure_notification,
            errors=["States.ALL"],
            result_path="$.Error"
        )

        phase2_task.add_catch(
            failure_notification,
            errors=["States.ALL"],
            result_path="$.Error"
        )

        phase3_task.add_catch(
            failure_notification,
            errors=["States.ALL"],
            result_path="$.Error"
        )

        phase45_task.add_catch(
            failure_notification,
            errors=["States.ALL"],
            result_path="$.Error"
        )

        phase6_task.add_catch(
            failure_notification,
            errors=["States.ALL"],
            result_path="$.Error"
        )

        # Chain the enhanced workflow (AgentCore integration + iterative cycles)
        definition = phase1_task \
            .next(parse_phase1_result) \
            .next(phase2_task) \
            .next(parse_phase2_result) \
            .next(phase3_task) \
            .next(parse_phase3_result) \
            .next(phase45_task) \
            .next(parse_phase45_result) \
            .next(phase6_task) \
            .next(parse_phase6_result) \
            .next(success_notification)

        # Create the state machine with X-Ray tracing
        self.state_machine = sfn.StateMachine(
            self, "Fleet6PhaseStateMachine",
            state_machine_name="fleet-6phase-pipeline",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            timeout=Duration.hours(2),
            comment="Fleet HIL 6-Phase Pipeline",
            tracing_enabled=True,
            logs=sfn.LogOptions(
                destination=self.log_group,
                level=sfn.LogLevel.ALL
            )
        )

        # Update S3 trigger Lambda with state machine ARN
        self.s3_trigger_lambda.add_environment("STATE_MACHINE_ARN", self.state_machine.state_machine_arn)

        # Grant Lambda permissions to start state machine
        self.state_machine.grant_start_execution(self.s3_trigger_lambda)

        # S3 Event Notification - Use specific prefix to avoid conflicts
        self.discovery_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(self.s3_trigger_lambda),
            s3.NotificationKeyFilter(
                prefix="raw-data/fleet-pipeline/",  # More specific prefix
                suffix=".bag"
            )
        )

        # Pipeline Outputs
        CfnOutput(self, "StateMachineArn",
            value=self.state_machine.state_machine_arn,
            description="Fleet Enhanced 6-Phase Pipeline State Machine ARN"
        )

        CfnOutput(self, "S3TriggerLambdaArn",
            value=self.s3_trigger_lambda.function_arn,
            description="S3 Trigger Lambda Function ARN"
        )

        # AWS Cognito User Pool for Fleet Discovery Authentication
        self.user_pool = cognito.UserPool(
            self, "FleetUserPool",
            user_pool_name=f"fleet-users-{unique_id}",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(
                email=True,
            ),
            auto_verify=cognito.AutoVerifiedAttrs(
                email=True,
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Cognito User Pool Client for Web Application
        self.user_pool_client = cognito.UserPoolClient(
            self, "FleetWebClient",
            user_pool=self.user_pool,
            user_pool_client_name=f"fleet-web-client-{unique_id}",
            auth_flows=cognito.AuthFlow(
                user_srp=True,
                user_password=False,
            ),
            generate_secret=False,
            refresh_token_validity=Duration.days(30),
            access_token_validity=Duration.minutes(60),
            id_token_validity=Duration.minutes(60),
            prevent_user_existence_errors=True,
        )

        # AgentCore Runtime ARN SSM Parameter Outputs
        CfnOutput(self, "SceneUnderstandingArnParam",
            value=self.ssm_scene_understanding_arn.parameter_name,
            description="SSM parameter for Scene Understanding Agent ARN - update after agent deployment"
        )
        CfnOutput(self, "AnomalyDetectionArnParam",
            value=self.ssm_anomaly_detection_arn.parameter_name,
            description="SSM parameter for Anomaly Detection Agent ARN - update after agent deployment"
        )
        CfnOutput(self, "SimilaritySearchArnParam",
            value=self.ssm_similarity_search_arn.parameter_name,
            description="SSM parameter for Similarity Search Agent ARN - update after agent deployment"
        )

        # Cognito Authentication Outputs for Frontend
        CfnOutput(self, "CognitoUserPoolId",
            value=self.user_pool.user_pool_id,
            description="Cognito User Pool ID for Fleet Discovery authentication"
        )
        CfnOutput(self, "CognitoUserPoolClientId",
            value=self.user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID for web application"
        )
        CfnOutput(self, "CognitoUserPoolArn",
            value=self.user_pool.user_pool_arn,
            description="Cognito User Pool ARN for Fleet Discovery"
        )

        # Create initial Cognito user from AUTH_USER/AUTH_PASSWORD env vars
        auth_user = os.environ.get("AUTH_USER", "")
        auth_password = os.environ.get("AUTH_PASSWORD", "")
        if auth_user and auth_password:
            create_user_lambda = lambda_.Function(
                self, "FleetCreateUserLambda",
                runtime=lambda_.Runtime.PYTHON_3_11,
                handler="index.handler",
                timeout=Duration.seconds(30),
                code=lambda_.Code.from_inline('''
import boto3
import cfnresponse

def handler(event, context):
    try:
        if event["RequestType"] == "Create":
            cognito = boto3.client("cognito-idp")
            props = event["ResourceProperties"]
            try:
                cognito.admin_create_user(
                    UserPoolId=props["UserPoolId"],
                    Username=props["Username"],
                    TemporaryPassword=props["Password"],
                    MessageAction="SUPPRESS",
                    UserAttributes=[{"Name": "email", "Value": props["Username"]}, {"Name": "email_verified", "Value": "true"}]
                )
                cognito.admin_set_user_password(
                    UserPoolId=props["UserPoolId"],
                    Username=props["Username"],
                    Password=props["Password"],
                    Permanent=True
                )
            except cognito.exceptions.UsernameExistsException:
                pass
        cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
    except Exception as e:
        print(f"Error: {e}")
        cfnresponse.send(event, context, cfnresponse.FAILED, {"Error": str(e)})
'''),
            )
            create_user_lambda.add_to_role_policy(iam.PolicyStatement(
                actions=["cognito-idp:AdminCreateUser", "cognito-idp:AdminSetUserPassword"],
                resources=[self.user_pool.user_pool_arn]
            ))
            CustomResource(
                self, "FleetInitialUser",
                service_token=create_user_lambda.function_arn,
                properties={
                    "UserPoolId": self.user_pool.user_pool_id,
                    "Username": auth_user,
                    "Password": auth_password,
                }
            )

        # APP RUNNER - Web API Service
        self._create_apprunner_service(unique_id)

        # CODEBUILD - Container Image Build Projects (must be after App Runner so we can add dependency)
        self._create_codebuild_projects(unique_id)

        # CDK-Nag Suppressions for patterns that cannot be fixed
        self._apply_nag_suppressions()

    def _create_apprunner_service(self, unique_id: str) -> None:
        """Create App Runner service for the Fleet Discovery web API"""

        # App Runner IAM role for ECR access
        apprunner_access_role = iam.Role(
            self, "FleetAppRunnerAccessRole",
            assumed_by=iam.ServicePrincipal("build.apprunner.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSAppRunnerServicePolicyForECRAccess")
            ]
        )

        # App Runner instance role for AWS service access
        apprunner_instance_role = iam.Role(
            self, "FleetAppRunnerInstanceRole",
            assumed_by=iam.ServicePrincipal("tasks.apprunner.amazonaws.com"),
        )

        # Grant permissions to instance role
        self.discovery_bucket.grant_read_write(apprunner_instance_role)
        self.vector_bucket.grant_read(apprunner_instance_role)
        apprunner_instance_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[
                "arn:aws:bedrock:*::foundation-model/cohere.embed-v4:0",
                "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v2:0",
                f"arn:aws:bedrock:{Stack.of(self).region}:{Stack.of(self).account}:inference-profile/us.cohere.embed-v4:0",
                f"arn:aws:bedrock:{Stack.of(self).region}:{Stack.of(self).account}:inference-profile/us.amazon.titan-embed-text-v2:0",
            ]
        ))
        apprunner_instance_role.add_to_policy(iam.PolicyStatement(
            actions=["sagemaker:InvokeEndpoint"],
            resources=[f"arn:aws:sagemaker:{Stack.of(self).region}:{Stack.of(self).account}:endpoint/endpoint-cosmos-embed1-text"]
        ))
        apprunner_instance_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "s3vectors:QueryVectors", "s3vectors:GetVectors",
                "s3vectors:ListVectors", "s3vectors:GetIndex",
                "s3vectors:ListIndexes", "s3vectors:GetVectorBucket",
                "s3vectors:ListVectorBuckets",
            ],
            resources=[f"arn:aws:s3vectors:{Stack.of(self).region}:{Stack.of(self).account}:*"]
        ))
        apprunner_instance_role.add_to_policy(iam.PolicyStatement(
            actions=["states:DescribeExecution", "states:ListExecutions"],
            resources=[self.state_machine.state_machine_arn, f"{self.state_machine.state_machine_arn}:*"]
        ))
        apprunner_instance_role.add_to_policy(iam.PolicyStatement(
            actions=["sts:GetCallerIdentity"],
            resources=["*"]
        ))

        # Create App Runner service from ECR image
        self.apprunner_service = apprunner.CfnService(
            self, "FleetWebApiService",
            service_name=f"fleet-web-api-{unique_id}",
            source_configuration=apprunner.CfnService.SourceConfigurationProperty(
                authentication_configuration=apprunner.CfnService.AuthenticationConfigurationProperty(
                    access_role_arn=apprunner_access_role.role_arn
                ),
                auto_deployments_enabled=True,
                image_repository=apprunner.CfnService.ImageRepositoryProperty(
                    image_identifier=f"{self.ecr_repo.repository_uri}:web-api-latest",
                    image_repository_type="ECR",
                    image_configuration=apprunner.CfnService.ImageConfigurationProperty(
                        port="8000",
                        runtime_environment_variables=[
                            apprunner.CfnService.KeyValuePairProperty(name="S3_BUCKET", value=self.discovery_bucket.bucket_name),
                            apprunner.CfnService.KeyValuePairProperty(name="VECTOR_BUCKET_NAME", value=self.vector_bucket.bucket_name),
                            apprunner.CfnService.KeyValuePairProperty(name="STATE_MACHINE_ARN", value=self.state_machine.state_machine_arn),
                            apprunner.CfnService.KeyValuePairProperty(name="AWS_REGION", value=Stack.of(self).region),
                            apprunner.CfnService.KeyValuePairProperty(name="COGNITO_USER_POOL_ID", value=self.user_pool.user_pool_id),
                            apprunner.CfnService.KeyValuePairProperty(name="COGNITO_CLIENT_ID", value=self.user_pool_client.user_pool_client_id),
                        ]
                    )
                )
            ),
            instance_configuration=apprunner.CfnService.InstanceConfigurationProperty(
                cpu="1024",
                memory="2048",
                instance_role_arn=apprunner_instance_role.role_arn
            ),
            health_check_configuration=apprunner.CfnService.HealthCheckConfigurationProperty(
                protocol="HTTP",
                path="/health",
                interval=10,
                timeout=5,
                healthy_threshold=1,
                unhealthy_threshold=5
            )
        )

        # Output the App Runner URL
        CfnOutput(self, "FleetWebApiUrl",
            value=f"https://{self.apprunner_service.attr_service_url}",
            description="Fleet Discovery Web API URL (auto-generated HTTPS)"
        )

        # Custom resource to set S3 CORS with exact App Runner URL
        cors_lambda = lambda_.Function(
            self, "FleetCorsConfigLambda",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            timeout=Duration.seconds(30),
            code=lambda_.Code.from_inline('''
import boto3
import json
import cfnresponse

def handler(event, context):
    try:
        if event["RequestType"] in ["Create", "Update"]:
            s3 = boto3.client("s3")
            bucket = event["ResourceProperties"]["BucketName"]
            origin = event["ResourceProperties"]["AllowedOrigin"]
            s3.put_bucket_cors(
                Bucket=bucket,
                CORSConfiguration={
                    "CORSRules": [{
                        "AllowedHeaders": ["*"],
                        "AllowedMethods": ["GET", "PUT", "POST", "HEAD", "DELETE"],
                        "AllowedOrigins": [origin],
                        "ExposeHeaders": ["ETag"],
                        "MaxAgeSeconds": 3000
                    }]
                }
            )
        cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
    except Exception as e:
        print(f"Error: {e}")
        cfnresponse.send(event, context, cfnresponse.FAILED, {"Error": str(e)})
'''),
        )
        self.discovery_bucket.grant_put_acl(cors_lambda)
        cors_lambda.add_to_role_policy(iam.PolicyStatement(
            actions=["s3:PutBucketCORS"],
            resources=[self.discovery_bucket.bucket_arn]
        ))

        CustomResource(
            self, "FleetCorsConfig",
            service_token=cors_lambda.function_arn,
            properties={
                "BucketName": self.discovery_bucket.bucket_name,
                "AllowedOrigin": f"https://{self.apprunner_service.attr_service_url}"
            }
        )

    def _apply_nag_suppressions(self) -> None:
        """Apply CDK-Nag suppressions for patterns that cannot be fixed"""
        NagSuppressions.add_stack_suppressions(self, [
            {"id": "AwsSolutions-COG2", "reason": "MFA requires Cognito Plus plan"},
            {"id": "AwsSolutions-COG3", "reason": "Advanced security requires Cognito Plus plan"},
            {"id": "AwsSolutions-IAM4", "reason": "Managed policies used for ECS/SSM standard permissions"},
            {"id": "AwsSolutions-IAM5", "reason": "Wildcard permissions scoped to specific services for pipeline operations"},
            {"id": "AwsSolutions-S1", "reason": "Access logs bucket cannot log to itself"},
            {"id": "CdkNagValidationFailure", "reason": "VPC CIDR intrinsic function cannot be validated statically"},
        ], apply_to_nested_stacks=True)

    def _create_ecs_security_group(self) -> ec2.SecurityGroup:
        """Create security group for ECS instances with minimal required access"""
        sg = ec2.SecurityGroup(
            self, "FleetECSSecurityGroup",
            vpc=self.vpc,
            description="Security group for Fleet ECS instances",
            allow_all_outbound=True
        )

        # Allow SSH within VPC only
        sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(22),
            description="Allow SSH within VPC for debugging"
        )

        return sg

    def _to_pascal_case(self, name: str) -> str:
        """Convert kebab-case to PascalCase for CDK construct names"""
        return ''.join(word.capitalize() for word in name.split('-'))

    def _get_s3_trigger_lambda_code(self) -> str:
        """Lambda code for S3 trigger"""
        return '''
import json
import boto3
import os
import re
from datetime import datetime

def lambda_handler(event, context):
    """
    Fleet Discovery Studio S3 Trigger Lambda
    Extracts scene_id from S3 path and triggers Step Functions
    """

    sfn_client = boto3.client('stepfunctions')
    state_machine_arn = os.environ['STATE_MACHINE_ARN']

    try:
        for record in event['Records']:
            bucket = record['s3']['bucket']['name']
            key = record['s3']['object']['key']

            # Extract scene_id from filename
            # Expected format: compressed-NuScenes-v1.0-trainval-scene-XXXX.bag
            scene_match = re.search(r'scene-([0-9]+)', key)
            if not scene_match:
                print(f"Could not extract scene_id from key: {key}")
                continue

            scene_id = f"scene-{scene_match.group(1)}"

            # Start Step Functions execution
            execution_input = {
                "scene_id": scene_id,
                "input_rosbag_key": key,
                "trigger_timestamp": datetime.utcnow().isoformat(),
                "source_bucket": bucket
            }

            response = sfn_client.start_execution(
                stateMachineArn=state_machine_arn,
                name=f"fleet-{scene_id}-{int(datetime.utcnow().timestamp())}",
                input=json.dumps(execution_input)
            )

            print(f"Started execution {response['executionArn']} for {scene_id}")

    except Exception as e:
        print(f"Error processing S3 event: {str(e)}")
        raise

    return {
        'statusCode': 200,
        'body': json.dumps('Successfully processed S3 events')
    }
'''

    def _create_codebuild_projects(self, unique_id: str) -> None:
        """Create CodeBuild projects and trigger them automatically during CDK deploy"""

        # Find the repo directory - use __file__ which is set by importlib
        import pathlib
        try:
            stack_file = pathlib.Path(__file__).resolve()
            repo_dir = stack_file.parent
            
            # Verify we found the right directory by checking for pipeline/
            # pipeline/ is at project root: 04-Vehicle_Data_Discovery/pipeline/
            # stack_file is at: 04-Vehicle_Data_Discovery/infra/cdk/fleet_discovery_cdk_stack.py
            for _ in range(3):  # Go up to 3 levels to find pipeline/
                if (repo_dir / "pipeline").exists():
                    break
                repo_dir = repo_dir.parent
            if not (repo_dir / "pipeline").exists():
                raise FileNotFoundError(f"Cannot find pipeline/ directory from {stack_file}")
                
            repo_dir_str = str(repo_dir)
            print(f"CodeBuild source directory: {repo_dir_str}")
        except Exception as e:
            print(f"Warning: Could not determine repo directory: {e}")
            # Fallback - skip source deployment, CodeBuild will fail but stack will deploy
            return

        # Upload source code to S3 for CodeBuild
        source_deployment = s3deploy.BucketDeployment(
            self, "FleetCodeBuildSource",
            sources=[s3deploy.Source.asset(repo_dir_str, exclude=[
                "*.pyc", "__pycache__", ".git", "cdk.out", "node_modules", 
                "output", ".venv", "*.egg-info", ".pytest_cache"
            ])],
            destination_bucket=self.discovery_bucket,
            destination_key_prefix="codebuild-source",
            memory_limit=1024,
        )

        # CodeBuild role
        codebuild_role = iam.Role(
            self, "FleetCodeBuildRole",
            role_name=f"fleet-codebuild-role-{unique_id}",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryPowerUser"),
            ]
        )
        codebuild_role.add_to_policy(iam.PolicyStatement(
            actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
            resources=["*"]
        ))
        self.discovery_bucket.grant_read(codebuild_role)
        self.ecr_repo.grant_pull_push(codebuild_role)

        # ARM64 build project
        self.arm64_build_project = codebuild.Project(
            self, "FleetARM64Build",
            project_name=f"fleet-arm64-build-{unique_id}",
            role=codebuild_role,
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxArmBuildImage.AMAZON_LINUX_2_STANDARD_3_0,
                compute_type=codebuild.ComputeType.LARGE,
                privileged=True,
            ),
            source=codebuild.Source.s3(bucket=self.discovery_bucket, path="codebuild-source/"),
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "phases": {
                    "pre_build": {"commands": [
                        "aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $ECR_REPO_URI"
                    ]},
                    "build": {"commands": [
                        "docker build -f infra/docker/Dockerfile.arm64 -t $ECR_REPO_URI:arm64-latest .",
                        "docker push $ECR_REPO_URI:arm64-latest"
                    ]}
                }
            }),
            environment_variables={"ECR_REPO_URI": codebuild.BuildEnvironmentVariable(value=self.ecr_repo.repository_uri)},
            timeout=Duration.minutes(15),
        )
        self.arm64_build_project.node.add_dependency(source_deployment)

        # GPU build project
        self.gpu_build_project = codebuild.Project(
            self, "FleetGPUBuild",
            project_name=f"fleet-gpu-build-{unique_id}",
            role=codebuild_role,
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.AMAZON_LINUX_2_5,
                compute_type=codebuild.ComputeType.LARGE,
                privileged=True,
            ),
            source=codebuild.Source.s3(bucket=self.discovery_bucket, path="codebuild-source/"),
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "phases": {
                    "pre_build": {"commands": [
                        "aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $ECR_REPO_URI"
                    ]},
                    "build": {"commands": [
                        "docker build -f infra/docker/Dockerfile.gpu -t $ECR_REPO_URI:gpu-amd64-latest .",
                        "docker push $ECR_REPO_URI:gpu-amd64-latest"
                    ]}
                }
            }),
            environment_variables={"ECR_REPO_URI": codebuild.BuildEnvironmentVariable(value=self.ecr_repo.repository_uri)},
            timeout=Duration.minutes(15),
        )
        self.gpu_build_project.node.add_dependency(source_deployment)

        # Web API build project (for App Runner) - must be x86_64 for App Runner
        self.webapi_build_project = codebuild.Project(
            self, "FleetWebApiBuild",
            project_name=f"fleet-webapi-build-{unique_id}",
            role=codebuild_role,
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.AMAZON_LINUX_2_5,
                compute_type=codebuild.ComputeType.SMALL,
                privileged=True,
            ),
            source=codebuild.Source.s3(bucket=self.discovery_bucket, path="codebuild-source/"),
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "phases": {
                    "install": {"runtime-versions": {"nodejs": "20"}},
                    "pre_build": {"commands": [
                        "aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $ECR_REPO_URI"
                    ]},
                    "build": {"commands": [
                        "docker build -f infra/docker/Dockerfile.webapp --build-arg COGNITO_USER_POOL_ID=$COGNITO_USER_POOL_ID --build-arg COGNITO_CLIENT_ID=$COGNITO_CLIENT_ID --build-arg AWS_REGION=$AWS_DEFAULT_REGION -t $ECR_REPO_URI:web-api-latest .",
                        "docker push $ECR_REPO_URI:web-api-latest"
                    ]}
                }
            }),
            environment_variables={
                "ECR_REPO_URI": codebuild.BuildEnvironmentVariable(value=self.ecr_repo.repository_uri),
                "COGNITO_USER_POOL_ID": codebuild.BuildEnvironmentVariable(value=self.user_pool.user_pool_id),
                "COGNITO_CLIENT_ID": codebuild.BuildEnvironmentVariable(value=self.user_pool_client.user_pool_client_id),
            },
            timeout=Duration.minutes(30),
        )
        self.webapi_build_project.node.add_dependency(source_deployment)

        # Lambda to trigger CodeBuild and wait for completion
        trigger_fn = lambda_.Function(
            self, "FleetBuildTrigger",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_inline('''
import boto3
import json
import time

def handler(event, context):
    print(f"Event: {json.dumps(event)}")
    if event["RequestType"] in ["Create", "Update"]:
        cb = boto3.client("codebuild")
        build_ids = []
        for proj in event["ResourceProperties"].get("Projects", []):
            try:
                resp = cb.start_build(projectName=proj)
                build_id = resp["build"]["id"]
                build_ids.append(build_id)
                print(f"Started {proj}: {build_id}")
            except Exception as e:
                print(f"Error starting {proj}: {e}")
        
        # Wait for all builds to complete
        if build_ids:
            print(f"Waiting for {len(build_ids)} builds to complete...")
            while True:
                resp = cb.batch_get_builds(ids=build_ids)
                statuses = [b["buildStatus"] for b in resp["builds"]]
                print(f"Build statuses: {statuses}")
                if all(s in ["SUCCEEDED", "FAILED", "STOPPED"] for s in statuses):
                    failed = [b["id"] for b in resp["builds"] if b["buildStatus"] != "SUCCEEDED"]
                    if failed:
                        raise Exception(f"Builds failed: {failed}")
                    print("All builds completed successfully")
                    break
                time.sleep(30)
    return {"PhysicalResourceId": event.get("PhysicalResourceId", "build-trigger")}
'''),
            timeout=Duration.minutes(15),
        )
        trigger_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["codebuild:StartBuild", "codebuild:BatchGetBuilds"],
            resources=[self.arm64_build_project.project_arn, self.gpu_build_project.project_arn, self.webapi_build_project.project_arn]
        ))

        # Custom resource provider and trigger - only build webapp for initial deploy
        # ARM64 and GPU builds can be triggered manually later for pipeline use
        provider = cr.Provider(self, "FleetBuildProvider", on_event_handler=trigger_fn)
        
        # Generate a hash of key source files to force rebuild when code changes
        def get_source_hash(directory):
            import hashlib
            h = hashlib.md5(usedforsecurity=False)
            for root, dirs, files in os.walk(directory):
                dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', 'cdk.out', '.venv']]
                for f in sorted(files):
                    if f.endswith('.py'):
                        filepath = os.path.join(root, f)
                        h.update(filepath.encode())
                        with open(filepath, 'rb') as fh:
                            h.update(fh.read())
            return h.hexdigest()[:12]
        
        source_hash = get_source_hash(repo_dir_str)
        
        build_trigger = CustomResource(
            self, "FleetBuildTriggerResource",
            service_token=provider.service_token,
            properties={
                "Projects": [self.arm64_build_project.project_name, self.gpu_build_project.project_name, self.webapi_build_project.project_name],
                "SourceHash": source_hash  # Forces update when source changes
            }
        )

        # Make App Runner depend on builds completing
        # Use CFN-level dependency since apprunner_service is an L1 CfnService
        self.apprunner_service.add_depends_on(build_trigger.node.default_child)

        # Outputs
        CfnOutput(self, "ECRRepositoryUri", value=self.ecr_repo.repository_uri, description="ECR Repository URI")
        CfnOutput(self, "ARM64BuildProjectName", value=self.arm64_build_project.project_name, description="ARM64 CodeBuild project")
        CfnOutput(self, "GPUBuildProjectName", value=self.gpu_build_project.project_name, description="GPU CodeBuild project")
        CfnOutput(self, "WebApiBuildProjectName", value=self.webapi_build_project.project_name, description="Web API CodeBuild project")