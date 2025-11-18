"""
Custom UI Construct for deploying agent-specific UIs (Streamlit, React, etc.)
"""

from aws_cdk import (
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
    aws_logs as logs,
    Duration,
    RemovalPolicy,
)
from constructs import Construct
from typing import Dict, Any


class CustomUIConstruct(Construct):
    """
    Deploys a custom UI (Streamlit, React, etc.) as a Fargate service
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        agent_name: str,
        agent_path: str,
        ui_config: Dict[str, Any],
        vpc: ec2.IVpc,
        cluster: ecs.ICluster,
        listener: elbv2.IApplicationListener,
        shared_resources: Dict[str, Any],
        auth_user: str,
        auth_password: str,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.agent_name = agent_name
        self.ui_config = ui_config
        
        # Create Fargate task definition
        self.task_definition = self._create_task_definition(
            agent_path, ui_config, shared_resources, auth_user, auth_password
        )
        
        # Create Fargate service
        self.service = self._create_fargate_service(vpc, cluster)
        
        # Add to ALB
        self._add_to_alb(listener, ui_config)

    def _create_task_definition(
        self, agent_path: str, ui_config: Dict[str, Any],
        shared_resources: Dict[str, Any], auth_user: str, auth_password: str
    ) -> ecs.FargateTaskDefinition:
        """Create Fargate task definition for the custom UI"""
        
        task_def = ecs.FargateTaskDefinition(
            self, "TaskDef",
            memory_limit_mib=512,
            cpu=256,
            execution_role=shared_resources.get('apprunner_access_role'),
            task_role=shared_resources.get('apprunner_instance_role')
        )
        
        # Create log group
        log_group = logs.LogGroup(
            self, "LogGroup",
            log_group_name=f"/aws/ecs/{self.agent_name}-ui",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK
        )
        
        # Get entrypoint from config
        entrypoint = ui_config.get('entrypoint', 'app.py')
        port = ui_config.get('port', 8501)
        
        # Build Docker image using common Streamlit Dockerfile
        import os
        dockerfile_dir = os.path.join(os.path.dirname(__file__), 'dockerfiles')
        
        # Add container
        container = task_def.add_container(
            "Container",
            image=ecs.ContainerImage.from_asset(
                agent_path,
                file=os.path.join(dockerfile_dir, 'Dockerfile.streamlit'),
                build_args={
                    "STREAMLIT_ENTRYPOINT": entrypoint
                }
            ),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="ui",
                log_group=log_group
            ),
            environment={
                "AUTH_USER": auth_user,
                "AUTH_PASSWORD": auth_password,
                "AWS_REGION": shared_resources.get('region', 'us-west-2'),
                "STREAMLIT_ENTRYPOINT": entrypoint,
            },
            port_mappings=[
                ecs.PortMapping(
                    container_port=port,
                    protocol=ecs.Protocol.TCP
                )
            ]
        )
        
        return task_def

    def _create_fargate_service(
        self, vpc: ec2.IVpc, cluster: ecs.ICluster
    ) -> ecs.FargateService:
        """Create Fargate service"""
        
        # Use private subnets if available, otherwise public
        has_private_subnets = len(vpc.private_subnets) > 0
        
        service = ecs.FargateService(
            self, "Service",
            cluster=cluster,
            task_definition=self.task_definition,
            desired_count=1,
            assign_public_ip=not has_private_subnets,  # Public IP only if no private subnets
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS if has_private_subnets else ec2.SubnetType.PUBLIC
            )
        )
        
        return service

    def _add_to_alb(
        self, listener: elbv2.IApplicationListener, ui_config: Dict[str, Any]
    ) -> None:
        """Add service to ALB with path-based routing"""
        
        # Create target group
        target_group = elbv2.ApplicationTargetGroup(
            self, "TargetGroup",
            vpc=self.service.cluster.vpc,
            port=ui_config.get('port', 8501),
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(
                path="/_stcore/health" if ui_config.get('type') == 'streamlit' else "/",
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                healthy_threshold_count=2,
                unhealthy_threshold_count=3
            ),
            deregistration_delay=Duration.seconds(30)
        )
        
        # Add Fargate service to target group
        target_group.add_target(self.service)
        
        # Add listener rule for path-based routing
        listener.add_action(
            f"{self.agent_name}Rule",
            priority=100,  # Lower priority than default
            conditions=[
                elbv2.ListenerCondition.path_patterns([f"{ui_config.get('path', '/')}/*"])
            ],
            action=elbv2.ListenerAction.forward([target_group])
        )
