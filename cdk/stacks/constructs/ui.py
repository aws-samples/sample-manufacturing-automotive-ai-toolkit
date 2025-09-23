from aws_cdk import (
    aws_codebuild as codebuild,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_ec2 as ec2,
    aws_s3 as s3,
    Duration,
    Stack
)
from constructs import Construct

class UIConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, resource_bucket: s3.Bucket, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Get default VPC
        vpc = ec2.Vpc.from_lookup(self, "DefaultVPC", is_default=True)
        
        # Create ECS cluster
        cluster = ecs.Cluster(self, "UICluster", vpc=vpc)
        
        # Create Fargate service with ALB
        self.fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "UIService",
            cluster=cluster,
            memory_limit_mib=2048,
            cpu=1024,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_asset("../ui"),
                container_port=3000,
            ),
            public_load_balancer=True,
            desired_count=1
        )
        
        # Health check
        self.fargate_service.target_group.configure_health_check(
            path="/",
            healthy_http_codes="200"
        )
