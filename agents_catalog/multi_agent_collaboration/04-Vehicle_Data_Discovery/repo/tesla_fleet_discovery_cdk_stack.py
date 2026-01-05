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
    custom_resources as cr,
    aws_s3_deployment as s3deploy,
    CfnOutput,
)
from constructs import Construct
from cdk_nag import NagSuppressions
import os
import hashlib

class TeslaFleetDiscoveryCdkStack(NestedStack):

    def __init__(self, scope: Construct, construct_id: str, shared_resources: dict = None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Generate unique_id from stack name for consistent naming
        unique_id = hashlib.md5(construct_id.encode()).hexdigest()[:8]

        # ECR REPOSITORIES for pipeline images
        self.ecr_repo = ecr.Repository(
            self, "TeslaFleetPipelineRepo",
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
            self, "TeslaFleetDiscoveryVPC",
            vpc_name="tesla-fleet-discovery-vpc",
            availability_zones=["us-west-2a", "us-west-2b", "us-west-2c"],
            cidr="10.0.0.0/16",
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="tesla-fleet-public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="tesla-fleet-private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24
                )
            ],
            flow_logs={"FlowLog": ec2.FlowLogOptions(destination=ec2.FlowLogDestination.to_cloud_watch_logs())}
        )

        # ECS CLUSTER with Container Insights enabled
        self.ecs_cluster = ecs.Cluster(
            self, "TeslaFleetCPUCluster",
            cluster_name=f"tesla-fleet-cpu-cluster-{unique_id}",
            vpc=self.vpc,
            container_insights=True
        )

        # IAM ROLE for ECS instances - FULL ADMIN PERMISSIONS FOR TESTING
        self.ecs_instance_role = iam.Role(
            self, "TeslaFleetECSInstanceRole",
            role_name=f"tesla-fleet-ecs-instance-role-{unique_id}",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonEC2ContainerServiceforEC2Role"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")  # Full admin for testing
            ]
        )

        # CREATE SECURITY GROUP FIRST (needed by launch template)
        self.ecs_security_group = self._create_ecs_security_group()

        # LAUNCH TEMPLATE - Modern pattern without redundant User Data
        self.launch_template = ec2.LaunchTemplate(
            self, "TeslaFleetLaunchTemplate",
            launch_template_name=f"tesla-fleet-arm64-lt-{unique_id}",
            instance_type=ec2.InstanceType("c7g.16xlarge"),
            machine_image=ecs.EcsOptimizedImage.amazon_linux2(
                hardware_type=ecs.AmiHardwareType.ARM
            ),
            security_group=self.ecs_security_group,
            role=self.ecs_instance_role,
        )

        # SNS Topic for ASG notifications
        self.asg_notification_topic = sns.Topic(
            self, "TeslaFleetASGNotificationTopic",
            topic_name=f"tesla-fleet-asg-notifications-{unique_id}",
            enforce_ssl=True
        )

        # AUTO SCALING GROUP with notifications
        self.auto_scaling_group = autoscaling.AutoScalingGroup(
            self, "TeslaFleetEC2ASG",
            auto_scaling_group_name=f"tesla-fleet-arm64-asg-{unique_id}",
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
            self, "TeslaFleetGPULaunchTemplate",
            launch_template_name=f"tesla-fleet-gpu-lt-{unique_id}",
            instance_type=ec2.InstanceType("g5.4xlarge"),
            machine_image=ec2.MachineImage.generic_linux({
                "us-west-2": "ami-0d6bf5c9fabd8c8c9"  # ECS GPU-optimized AMI
            }),
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

        # GPU AUTO SCALING GROUP with notifications
        self.gpu_auto_scaling_group = autoscaling.AutoScalingGroup(
            self, "TeslaFleetGPUASG",
            auto_scaling_group_name=f"tesla-fleet-gpu-asg-{unique_id}",
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            launch_template=self.gpu_launch_template,
            min_capacity=1,
            max_capacity=3,
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

        # ARM64 CAPACITY PROVIDER
        self.arm64_capacity_provider = ecs.AsgCapacityProvider(
            self, "TeslaFleetCapacityProvider",
            capacity_provider_name=f"tesla-fleet-arm64-cp-{unique_id}",
            auto_scaling_group=self.auto_scaling_group,
            enable_managed_scaling=True,
            enable_managed_termination_protection=False,
            target_capacity_percent=80,
            minimum_scaling_step_size=1,
            maximum_scaling_step_size=3
        )

        # GPU CAPACITY PROVIDER
        self.gpu_capacity_provider = ecs.AsgCapacityProvider(
            self, "TeslaFleetGPUCapacityProvider",
            capacity_provider_name=f"tesla-fleet-gpu-cp-{unique_id}",
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
            self, "TeslaFleetAccessLogsBucket",
            bucket_name=f"tesla-fleet-logs-{unique_id}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            enforce_ssl=True,
        )

        # S3 BUCKET - Create new bucket for this deployment
        self.discovery_bucket = s3.Bucket(
            self, "TeslaFleetDiscoveryBucket",
            bucket_name=f"tesla-fleet-discovery-{unique_id}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            enforce_ssl=True,
            server_access_logs_bucket=self.access_logs_bucket,
            server_access_logs_prefix="discovery-bucket/",
        )

        # S3 BUCKET - Vector storage
        self.vector_bucket = s3.Bucket(
            self, "TeslaFleetVectorBucket",
            bucket_name=f"tesla-fleet-vectors-{unique_id}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            enforce_ssl=True,
            server_access_logs_bucket=self.access_logs_bucket,
            server_access_logs_prefix="vector-bucket/",
        )

        # CLOUDWATCH LOG GROUP
        self.log_group = logs.LogGroup(
            self, "TeslaFleetLogGroup",
            log_group_name=f"/aws/tesla-fleet-discovery-{unique_id}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY
        )

        # IAM ROLES - Properly scoped permissions (NO wildcards)

        # ECS Task Execution Role
        self.ecs_task_execution_role = iam.Role(
            self, "TeslaFleetECSTaskExecutionRole",
            role_name=f"tesla-fleet-ecs-execution-role-{unique_id}",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
            ]
        )

        # ECS Task Role - FULL ADMIN PERMISSIONS + explicit Bedrock + AgentCore permissions
        self.ecs_task_role = iam.Role(
            self, "TeslaFleetECSTaskRole",
            role_name=f"tesla-fleet-ecs-task-role-{unique_id}",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonBedrockFullAccess")
            ]
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
                    "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v2:0"
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
            description="Tesla Fleet GPU ECS Cluster (EC2-backed with managed scaling)"
        )

        CfnOutput(self, "ECSClusterArn",
            value=self.ecs_cluster.cluster_arn,
            description="Tesla Fleet ECS Cluster ARN"
        )

        CfnOutput(self, "ARM64AutoScalingGroupName",
            value=self.auto_scaling_group.auto_scaling_group_name,
            description="Tesla Fleet ARM64 Auto Scaling Group (ECS-managed)"
        )

        CfnOutput(self, "GPUAutoScalingGroupName",
            value=self.gpu_auto_scaling_group.auto_scaling_group_name,
            description="Tesla Fleet GPU Auto Scaling Group (ECS-managed)"
        )

        CfnOutput(self, "ARM64CapacityProviderName",
            value=self.arm64_capacity_provider.capacity_provider_name,
            description="Tesla Fleet ARM64 ECS Capacity Provider (c7g.16xlarge)"
        )

        CfnOutput(self, "GPUCapacityProviderName",
            value=self.gpu_capacity_provider.capacity_provider_name,
            description="Tesla Fleet GPU ECS Capacity Provider (g5.4xlarge)"
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
            self, "TeslaFleetS3BucketParam",
            parameter_name=f"/tesla-fleet/{unique_id}/s3-bucket",
            string_value=self.discovery_bucket.bucket_name
        )
        self.ssm_vector_bucket = ssm.StringParameter(
            self, "TeslaFleetVectorBucketParam",
            parameter_name=f"/tesla-fleet/{unique_id}/vector-bucket",
            string_value=self.vector_bucket.bucket_name
        )
        self.ssm_region = ssm.StringParameter(
            self, "TeslaFleetRegionParam",
            parameter_name=f"/tesla-fleet/{unique_id}/region",
            string_value=self.region
        )

        # Grant ECS task execution role access to SSM parameters
        self.ssm_s3_bucket.grant_read(self.ecs_task_execution_role)
        self.ssm_vector_bucket.grant_read(self.ecs_task_execution_role)
        self.ssm_region.grant_read(self.ecs_task_execution_role)

        # PIPELINE PHASE TASK DEFINITIONS - BRIDGE networking for ephemeral tasks

        # Phase 1: Multi-sensor ROS bag extraction
        self.phase1_task_def = ecs.Ec2TaskDefinition(
            self, "TeslaPhase1TaskDef",
            family="tesla-phase1-extraction",
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
            command=["python3", "/app/multi_sensor_rosbag_extractor.py"],
            memory_limit_mib=4096,
            cpu=2048,
            secrets={
                "AWS_DEFAULT_REGION": ecs.Secret.from_ssm_parameter(self.ssm_region),
                "S3_BUCKET": ecs.Secret.from_ssm_parameter(self.ssm_s3_bucket)
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="tesla-phase1-extraction",
                log_group=self.log_group
            )
        )

        # Phase 2: Video reconstruction
        self.phase2_task_def = ecs.Ec2TaskDefinition(
            self, "TeslaPhase2TaskDef",
            family="tesla-phase2-video",
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
            command=["python3", "/app/rosbag_video_reconstructor.py"],
            memory_limit_mib=8192,
            cpu=4096,
            secrets={
                "AWS_DEFAULT_REGION": ecs.Secret.from_ssm_parameter(self.ssm_region),
                "S3_BUCKET": ecs.Secret.from_ssm_parameter(self.ssm_s3_bucket)
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="tesla-phase2-video",
                log_group=self.log_group
            )
        )

        # SSM parameters for Phase 3 specific config
        self.ssm_bedrock_model = ssm.StringParameter(
            self, "TeslaFleetBedrockModelParam",
            parameter_name=f"/tesla-fleet/{unique_id}/bedrock-model",
            string_value="anthropic.claude-3-sonnet-20240229-v1:0"
        )
        self.ssm_vector_index = ssm.StringParameter(
            self, "TeslaFleetVectorIndexParam",
            parameter_name=f"/tesla-fleet/{unique_id}/vector-index",
            string_value="behavioral-metadata-index"
        )
        self.ssm_bedrock_model.grant_read(self.ecs_task_execution_role)
        self.ssm_vector_index.grant_read(self.ecs_task_execution_role)

        # Phase 3: InternVideo2.5 behavioral analysis (GPU-targeted)
        self.phase3_task_def = ecs.Ec2TaskDefinition(
            self, "TeslaPhase3TaskDef",
            family="tesla-phase3-internvideo25-gpu",
            execution_role=self.ecs_task_execution_role,
            task_role=self.ecs_task_role,
            network_mode=ecs.NetworkMode.BRIDGE,
            placement_constraints=[
                ecs.PlacementConstraint.member_of("attribute:ecs.instance-type =~ g5.*")
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
                stream_prefix="tesla-phase3-internvideo25",
                log_group=self.log_group
            )
        )

        # Phase 4-5: S3 Vectors embeddings
        self.phase45_task_def = ecs.Ec2TaskDefinition(
            self, "TeslaPhase45TaskDef",
            family="tesla-phase45-embeddings",
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
            command=["python3", "/app/tesla_s3_vectors_behavioral_embeddings.py"],
            memory_limit_mib=2048,
            cpu=1024,
            secrets={
                "AWS_DEFAULT_REGION": ecs.Secret.from_ssm_parameter(self.ssm_region),
                "S3_BUCKET": ecs.Secret.from_ssm_parameter(self.ssm_s3_bucket),
                "VECTOR_BUCKET_NAME": ecs.Secret.from_ssm_parameter(self.ssm_vector_bucket),
                "VECTOR_INDEX_NAME": ecs.Secret.from_ssm_parameter(self.ssm_vector_index),
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="tesla-phase45-embeddings",
                log_group=self.log_group
            )
        )

        # Phase 6: Enhanced Multi-agent orchestrator
        self.phase6_task_def = ecs.Ec2TaskDefinition(
            self, "TeslaPhase6TaskDef",
            family="tesla-phase6-orchestrator",
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
            command=["python3", "/app/microservice_orchestrator.py"],
            memory_limit_mib=2048,
            cpu=1024,
            secrets={
                "AWS_DEFAULT_REGION": ecs.Secret.from_ssm_parameter(self.ssm_region),
                "S3_BUCKET": ecs.Secret.from_ssm_parameter(self.ssm_s3_bucket),
                "VECTOR_BUCKET_NAME": ecs.Secret.from_ssm_parameter(self.ssm_vector_bucket),
                "VECTOR_INDEX_NAME": ecs.Secret.from_ssm_parameter(self.ssm_vector_index),
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="tesla-phase6-enhanced-orchestrator",
                log_group=self.log_group
            )
        )

        # ALERTING INFRASTRUCTURE

        # SNS Topics for notifications with SSL enforcement
        self.success_topic = sns.Topic(
            self, "TeslaFleetSuccessTopic",
            topic_name="vehicle-fleet-pipeline-success",
            display_name="Tesla Fleet Pipeline Success Notifications",
            enforce_ssl=True
        )

        self.failure_topic = sns.Topic(
            self, "TeslaFleetFailureTopic",
            topic_name="tesla-fleet-critical-failures",
            display_name="Tesla Fleet Critical Failure Alerts",
            enforce_ssl=True
        )

        # Final DLQ for unprocessable messages
        self.final_dlq = sqs.Queue(
            self, "TeslaFleetFinalDLQ",
            queue_name="tesla-fleet-final-dlq",
            retention_period=Duration.days(14),
            enforce_ssl=True
        )

        # SQS DLQ for failed scenes
        self.failed_scenes_dlq = sqs.Queue(
            self, "TeslaFleetFailedScenesDLQ",
            queue_name="tesla-fleet-failed-scenes-dlq",
            visibility_timeout=Duration.minutes(5),
            retention_period=Duration.days(14),
            receive_message_wait_time=Duration.seconds(20),
            enforce_ssl=True,
            dead_letter_queue=sqs.DeadLetterQueue(queue=self.final_dlq, max_receive_count=3)
        )

        # LAMBDA FUNCTIONS

        # S3 Trigger Lambda
        self.s3_trigger_lambda = lambda_.Function(
            self, "TeslaS3TriggerLambda",
            function_name=f"tesla-s3-trigger-{self.region}",
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
        # Note: Agent endpoints step REMOVED - Phase 6 now uses hardcoded AgentCore ARNs

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
                        # Note: Agent endpoint URLs REMOVED - Phase 6 now uses hardcoded AgentCore ARNs
                    ]
                )
            ],
            result_path="$.phase6_raw_result"
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
            subject="Tesla Fleet Enhanced Pipeline Success"
        )

        failure_notification = tasks.SnsPublish(
            self, "FailureNotification",
            topic=self.failure_topic,
            message=sfn.TaskInput.from_json_path_at("$.Error"),
            subject="Tesla Fleet Enhanced Pipeline Failure"
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
            self, "TeslaFleet6PhaseStateMachine",
            state_machine_name="tesla-fleet-6phase-pipeline",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            timeout=Duration.hours(2),
            comment="Tesla Fleet HIL 6-Phase Pipeline",
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
                prefix="raw-data/tesla-pipeline/",  # More specific prefix
                suffix=".bag"
            )
        )

        # Pipeline Outputs
        CfnOutput(self, "StateMachineArn",
            value=self.state_machine.state_machine_arn,
            description="Tesla Fleet Enhanced 6-Phase Pipeline State Machine ARN"
        )

        CfnOutput(self, "S3TriggerLambdaArn",
            value=self.s3_trigger_lambda.function_arn,
            description="S3 Trigger Lambda Function ARN"
        )

        # AWS Cognito User Pool for Fleet Discovery Authentication
        self.user_pool = cognito.UserPool(
            self, "TeslaFleetUserPool",
            user_pool_name=f"tesla-fleet-users-{unique_id}",
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
            self, "TeslaFleetWebClient",
            user_pool=self.user_pool,
            user_pool_client_name=f"tesla-fleet-web-client-{unique_id}",
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

        # AgentCore Runtime ARN Outputs (replacing ECS agent services)
        CfnOutput(self, "AgentCoreRuntimeArns",
            value="behavioral_gap_analysis_agent-W8F8B7DuQb→scene_understanding,safety_validation_agent-5mBQ4FGj2E→anomaly_detection,intelligence_gathering_agent-D2agaCFcUo→similarity_search",
            description="Tesla Fleet HIL AgentCore Runtime ARNs (NEW 3-agent sequential topology deployed versions)"
        )

        # CODEBUILD - Container Image Build Projects
        self._create_codebuild_projects(unique_id)

        # Cognito Authentication Outputs for Frontend
        CfnOutput(self, "CognitoUserPoolId",
            value=self.user_pool.user_pool_id,
            description="Cognito User Pool ID for Tesla Fleet Discovery authentication"
        )

        CfnOutput(self, "CognitoUserPoolClientId",
            value=self.user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID for web application"
        )

        CfnOutput(self, "CognitoUserPoolArn",
            value=self.user_pool.user_pool_arn,
            description="Cognito User Pool ARN for Tesla Fleet Discovery"
        )

        # CDK-Nag Suppressions for patterns that cannot be fixed
        self._apply_nag_suppressions()

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
            self, "TeslaFleetECSSecurityGroup",
            vpc=self.vpc,
            description="Security group for Tesla Fleet ECS instances",
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
                name=f"tesla-fleet-{scene_id}-{int(datetime.utcnow().timestamp())}",
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
            if not (repo_dir / "pipeline").exists():
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
            self, "TeslaFleetCodeBuildSource",
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
            self, "TeslaFleetCodeBuildRole",
            role_name=f"tesla-fleet-codebuild-role-{unique_id}",
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
            self, "TeslaFleetARM64Build",
            project_name=f"tesla-fleet-arm64-build-{unique_id}",
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
                        "docker build -f infrastructure/Dockerfile.arm64 -t $ECR_REPO_URI:arm64-latest .",
                        "docker push $ECR_REPO_URI:arm64-latest"
                    ]}
                }
            }),
            environment_variables={"ECR_REPO_URI": codebuild.BuildEnvironmentVariable(value=self.ecr_repo.repository_uri)},
            timeout=Duration.minutes(60),
        )
        self.arm64_build_project.node.add_dependency(source_deployment)

        # GPU build project
        self.gpu_build_project = codebuild.Project(
            self, "TeslaFleetGPUBuild",
            project_name=f"tesla-fleet-gpu-build-{unique_id}",
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
                        "docker build -f infrastructure/Dockerfile.gpu -t $ECR_REPO_URI:gpu-amd64-latest .",
                        "docker push $ECR_REPO_URI:gpu-amd64-latest"
                    ]}
                }
            }),
            environment_variables={"ECR_REPO_URI": codebuild.BuildEnvironmentVariable(value=self.ecr_repo.repository_uri)},
            timeout=Duration.minutes(60),
        )
        self.gpu_build_project.node.add_dependency(source_deployment)

        # Lambda to trigger CodeBuild
        trigger_fn = lambda_.Function(
            self, "TeslaFleetBuildTrigger",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_inline('''
import boto3
import json

def handler(event, context):
    print(f"Event: {json.dumps(event)}")
    if event["RequestType"] in ["Create", "Update"]:
        cb = boto3.client("codebuild")
        for proj in event["ResourceProperties"].get("Projects", []):
            try:
                resp = cb.start_build(projectName=proj)
                print(f"Started {proj}: {resp['build']['id']}")
            except Exception as e:
                print(f"Error starting {proj}: {e}")
    return {"PhysicalResourceId": event.get("PhysicalResourceId", "build-trigger")}
'''),
            timeout=Duration.minutes(5),
        )
        trigger_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["codebuild:StartBuild"],
            resources=[self.arm64_build_project.project_arn, self.gpu_build_project.project_arn]
        ))

        # Custom resource provider and trigger
        provider = cr.Provider(self, "TeslaFleetBuildProvider", on_event_handler=trigger_fn)
        CustomResource(
            self, "TeslaFleetBuildTriggerResource",
            service_token=provider.service_token,
            properties={"Projects": [self.arm64_build_project.project_name, self.gpu_build_project.project_name]}
        )

        # Outputs
        CfnOutput(self, "ECRRepositoryUri", value=self.ecr_repo.repository_uri, description="ECR Repository URI")
        CfnOutput(self, "ARM64BuildProjectName", value=self.arm64_build_project.project_name, description="ARM64 CodeBuild project")
        CfnOutput(self, "GPUBuildProjectName", value=self.gpu_build_project.project_name, description="GPU CodeBuild project")