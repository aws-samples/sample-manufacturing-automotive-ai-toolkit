#!/usr/bin/env python3
"""
Fleet Discovery Studio - Web Stack (CDK)
Separate web deployment stack for FastAPI + Next.js frontend
Uses AWS App Runner for serverless container deployment with custom domain
"""

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_apprunner as apprunner,
    aws_iam as iam,
    aws_certificatemanager as acm,
    aws_route53 as route53,
    CfnOutput,
)
from constructs import Construct


class TeslaWebStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Domain configuration
        domain_name = "auto-mfg-pvt-ltd.co"
        api_subdomain = f"api.{domain_name}"

        # Use existing Route 53 Hosted Zone
        hosted_zone = route53.HostedZone.from_hosted_zone_attributes(
            self, "TeslaDomainHostedZone",
            hosted_zone_id="Z0811780X1GI1WS4J0VJ",
            zone_name=domain_name
        )

        # IAM Role for App Runner Service (ECR Access)
        apprunner_execution_role = iam.Role(
            self, "AppRunnerExecutionRole",
            assumed_by=iam.ServicePrincipal("build.apprunner.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSAppRunnerServicePolicyForECRAccess")
            ]
        )

        # App Runner Instance Role (for runtime permissions)
        apprunner_instance_role = iam.Role(
            self, "AppRunnerInstanceRole",
            assumed_by=iam.ServicePrincipal("tasks.apprunner.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
            ]
        )

        # Use existing ECR repository
        import aws_cdk.aws_ecr as ecr
        web_api_repo = ecr.Repository.from_repository_name(
            self, "TeslaWebApiRepo",
            repository_name="tesla-web-api"
        )

        # App Runner Service for FastAPI Backend
        # This will run our containerized FastAPI app
        app_runner_service = apprunner.CfnService(
            self, "TeslaApiService",
            service_name="tesla-fleet-api",
            source_configuration=apprunner.CfnService.SourceConfigurationProperty(
                image_repository=apprunner.CfnService.ImageRepositoryProperty(
                    image_identifier=f"{web_api_repo.repository_uri}:latest",
                    image_configuration=apprunner.CfnService.ImageConfigurationProperty(
                        port="8000",
                        runtime_environment_variables=[
                            apprunner.CfnService.KeyValuePairProperty(
                                name="AWS_DEFAULT_REGION",
                                value="us-west-2"
                            ),
                            apprunner.CfnService.KeyValuePairProperty(
                                name="PORT",
                                value="8000"
                            )
                        ]
                    ),
                    image_repository_type="ECR"
                ),
                authentication_configuration=apprunner.CfnService.AuthenticationConfigurationProperty(
                    access_role_arn=apprunner_execution_role.role_arn
                ),
                auto_deployments_enabled=True
            ),
            instance_configuration=apprunner.CfnService.InstanceConfigurationProperty(
                cpu="4096",  # 4 vCPU (upgraded from 2048)
                memory="12288",  # 12 GB RAM (upgraded from 4096)
                instance_role_arn=apprunner_instance_role.role_arn
            ),
            health_check_configuration=apprunner.CfnService.HealthCheckConfigurationProperty(
                protocol="HTTP",
                path="/",
                interval=10,          # Check every 10 seconds (gives app time to breathe)
                timeout=10,           # Allow 10 seconds for the app to respond
                healthy_threshold=1,  # It only needs to work once to be "live"
                unhealthy_threshold=5 # Allow it to fail 5 times (50s total) before restarting
            )
        )

        # SSL Certificate for custom domain with Route 53 DNS validation
        certificate = acm.Certificate(
            self, "TeslaDomainCertificate",
            domain_name=api_subdomain,
            validation=acm.CertificateValidation.from_dns(hosted_zone)
        )

        # Note: Custom Domain Association needs to be configured manually in AWS Console
        # or via AWS CLI after App Runner service is deployed
        # The CDK construct for domain association may not be available in this version

        # Outputs for reference
        CfnOutput(
            self, "AppRunnerServiceUrl",
            value=f"https://{app_runner_service.attr_service_url}",
            description="App Runner service URL"
        )

        CfnOutput(
            self, "CustomDomainUrl",
            value=f"https://{api_subdomain}",
            description="Custom domain URL for the API"
        )

        CfnOutput(
            self, "ECRRepositoryUri",
            value=web_api_repo.repository_uri,
            description="ECR repository URI for web API Docker images"
        )

        CfnOutput(
            self, "DNSValidationRecords",
            value="Check AWS Certificate Manager console for DNS validation records",
            description="DNS records needed for domain validation"
        )

        # Store important attributes for later reference
        self.app_runner_service = app_runner_service
        self.web_api_repo = web_api_repo
        self.certificate = certificate
        self.domain_name = api_subdomain