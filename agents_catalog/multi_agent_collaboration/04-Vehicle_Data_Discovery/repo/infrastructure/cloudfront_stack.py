#!/usr/bin/env python3
"""
Fleet Discovery Studio - CloudFront Distribution Stack
Path-based routing: auto-mfg-pvt-ltd.co → Frontend, auto-mfg-pvt-ltd.co/api/* → App Runner
"""
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_certificatemanager as acm,
    aws_route53 as route53,
    aws_route53_targets as targets,
    CfnOutput,
)
from constructs import Construct


class TeslaCloudFrontStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Domain configuration
        domain_name = "auto-mfg-pvt-ltd.co"
        app_runner_domain = "6kicn2wbzm.us-west-2.awsapprunner.com"

        # Use existing Route 53 Hosted Zone
        hosted_zone = route53.HostedZone.from_hosted_zone_attributes(
            self, "TeslaDomainHostedZone",
            hosted_zone_id="Z0811780X1GI1WS4J0VJ",
            zone_name=domain_name
        )

        # Create S3 bucket for frontend hosting
        frontend_bucket = s3.Bucket(
            self, "TeslaFrontendBucket",
            bucket_name=f"tesla-frontend-{domain_name.replace('.', '-')}-{self.account}",
            public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            versioned=False
        )

        # SSL Certificate for custom domain
        certificate = acm.Certificate(
            self, "TeslaDomainCertificate",
            domain_name=domain_name,
            validation=acm.CertificateValidation.from_dns(hosted_zone)
        )

        # Origin Access Identity for S3 (using OAI instead of OAC for compatibility)
        origin_access_identity = cloudfront.OriginAccessIdentity(
            self, "TeslaOriginAccessIdentity",
            comment="OAI for Tesla Frontend S3 Bucket"
        )

        # CloudFront Distribution with dual origins
        distribution = cloudfront.Distribution(
            self, "TeslaDistribution",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                # Default behavior: serve frontend from S3
                origin=origins.S3Origin(
                    frontend_bucket,
                    origin_access_identity=origin_access_identity
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                compress=True,
            ),
            additional_behaviors={
                # API behavior: route /api/* to App Runner
                "/api/*": cloudfront.BehaviorOptions(
                    origin=origins.HttpOrigin(
                        app_runner_domain,
                        protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
                        custom_headers={
                            "X-Forwarded-Host": domain_name
                        }
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,  # Don't cache API responses
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                    compress=False,  # Don't compress API responses
                )
            },
            domain_names=[domain_name],
            certificate=certificate,
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            error_responses=[
                # SPA routing - redirect 404s to index.html
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(5)
                ),
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(5)
                )
            ],
            comment=f"Tesla Fleet Discovery Studio - {domain_name}",
            enabled=True,
            price_class=cloudfront.PriceClass.PRICE_CLASS_ALL,
            http_version=cloudfront.HttpVersion.HTTP2
        )

        # Update Route 53 to point domain to CloudFront
        route53.ARecord(
            self, "TeslaDomainRecord",
            zone=hosted_zone,
            record_name=domain_name,
            target=route53.RecordTarget.from_alias(
                targets.CloudFrontTarget(distribution)
            )
        )

        # Deploy frontend files to S3 bucket
        # Note: Frontend files are built from frontend/tesla-discovery-studio/
        frontend_deployment = s3deploy.BucketDeployment(
            self, "TeslaFrontendDeployment",
            sources=[s3deploy.Source.asset("./frontend/tesla-discovery-studio/out/")],
            destination_bucket=frontend_bucket,
            distribution=distribution,
            distribution_paths=["/*"],
            retain_on_delete=False,
            memory_limit=512  # Increase from default 128MB to 512MB for better performance
        )

        # Grant CloudFront access to S3 bucket via OAI
        frontend_bucket.grant_read(origin_access_identity)

        # Outputs
        CfnOutput(
            self, "CloudFrontDistributionId",
            value=distribution.distribution_id,
            description="CloudFront Distribution ID"
        )

        CfnOutput(
            self, "CloudFrontDomainName",
            value=distribution.distribution_domain_name,
            description="CloudFront Distribution Domain Name"
        )

        CfnOutput(
            self, "WebsiteURL",
            value=f"https://{domain_name}",
            description="Tesla Fleet Discovery Studio Website URL"
        )

        CfnOutput(
            self, "APIURL",
            value=f"https://{domain_name}/api",
            description="Tesla Fleet Discovery API URL"
        )

        CfnOutput(
            self, "S3BucketName",
            value=frontend_bucket.bucket_name,
            description="S3 bucket name for frontend hosting"
        )

        # Store important attributes
        self.distribution = distribution
        self.frontend_bucket = frontend_bucket
        self.certificate = certificate
        self.hosted_zone = hosted_zone