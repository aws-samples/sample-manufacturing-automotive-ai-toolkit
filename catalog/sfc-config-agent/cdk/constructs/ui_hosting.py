"""
WP-18 — CloudFront + S3 UI Hosting CDK Construct.

Provisions:
  - CloudFront distribution with two origins:
      * S3 (OAC)  — serves static SPA from SfcConfigBucket/ui/*  (default origin)
      * API GW    — forwards /api/* to the HTTP API (no cache)
  - Origin Access Control (OAC) for the S3 origin
  - S3 bucket policy allowing CloudFront OAC reads on /ui/*
  - Custom error responses for SPA client-side routing (403 → 200 /index.html)
  - HTTPS-only viewer protocol
"""

from __future__ import annotations

from aws_cdk import (
    CfnOutput,
    Stack,
    aws_cloudfront as cf,
    aws_cloudfront_origins as origins,
    aws_iam as iam,
    aws_s3 as s3,
)
from constructs import Construct


class UiHosting(Construct):
    """CloudFront distribution that serves the SFC Control Plane SPA."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        configs_bucket: s3.IBucket,
        http_api,           # apigwv2.CfnApi
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        account = Stack.of(self).account
        region = Stack.of(self).region

        # ----------------------------------------------------------------
        # Origin Access Control (replaces legacy OAI)
        # ----------------------------------------------------------------
        oac = cf.CfnOriginAccessControl(
            self,
            "SfcUiOac",
            origin_access_control_config=cf.CfnOriginAccessControl.OriginAccessControlConfigProperty(
                name="SfcControlPlaneUiOac",
                origin_access_control_origin_type="s3",
                signing_behavior="always",
                signing_protocol="sigv4",
                description="OAC for SFC Control Plane UI S3 origin",
            ),
        )

        # ----------------------------------------------------------------
        # API Gateway origin (HTTP API)
        # api_url has the form https://{id}.execute-api.{region}.amazonaws.com
        # We use Fn.select / Fn.split to strip the scheme for the origin domain.
        # ----------------------------------------------------------------
        from aws_cdk import Fn
        api_domain = Fn.select(
            2,
            Fn.split("/", f"https://{http_api.ref}.execute-api.{region}.amazonaws.com/"),
        )

        # ----------------------------------------------------------------
        # CloudFront Distribution (L1 — CfnDistribution)
        # We use L1 so we can attach OAC (not supported by L2 at CDK 2.x).
        # ----------------------------------------------------------------
        self.distribution = cf.CfnDistribution(
            self,
            "SfcUiDistribution",
            distribution_config=cf.CfnDistribution.DistributionConfigProperty(
                enabled=True,
                default_root_object="index.html",
                price_class="PriceClass_100",
                http_version="http2",
                comment="SFC Control Plane UI",

                # ── Origins ──────────────────────────────────────────────
                origins=[
                    # S3 origin — serves SPA static assets from /ui/ prefix
                    cf.CfnDistribution.OriginProperty(
                        id="S3UiOrigin",
                        domain_name=configs_bucket.bucket_regional_domain_name,
                        origin_path="/ui",
                        s3_origin_config=cf.CfnDistribution.S3OriginConfigProperty(
                            origin_access_identity="",  # empty when using OAC
                        ),
                        origin_access_control_id=oac.ref,
                    ),
                    # API Gateway origin — proxies /api/* requests
                    cf.CfnDistribution.OriginProperty(
                        id="ApiGwOrigin",
                        domain_name=f"{http_api.ref}.execute-api.{region}.amazonaws.com",
                        custom_origin_config=cf.CfnDistribution.CustomOriginConfigProperty(
                            https_port=443,
                            origin_protocol_policy="https-only",
                            origin_ssl_protocols=["TLSv1.2"],
                        ),
                    ),
                ],

                # ── Cache Behaviours ──────────────────────────────────────
                default_cache_behavior=cf.CfnDistribution.DefaultCacheBehaviorProperty(
                    target_origin_id="S3UiOrigin",
                    viewer_protocol_policy="redirect-to-https",
                    cache_policy_id=cf.CachePolicy.CACHING_OPTIMIZED.cache_policy_id,
                    compress=True,
                    allowed_methods=["GET", "HEAD", "OPTIONS"],
                    cached_methods=["GET", "HEAD"],
                ),
                cache_behaviors=[
                    cf.CfnDistribution.CacheBehaviorProperty(
                        path_pattern="/api/*",
                        target_origin_id="ApiGwOrigin",
                        viewer_protocol_policy="redirect-to-https",
                        cache_policy_id=cf.CachePolicy.CACHING_DISABLED.cache_policy_id,
                        origin_request_policy_id=cf.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER.origin_request_policy_id,
                        allowed_methods=["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"],
                        cached_methods=["GET", "HEAD"],
                        compress=False,
                    ),
                ],

                # ── SPA custom error responses ────────────────────────────
                custom_error_responses=[
                    cf.CfnDistribution.CustomErrorResponseProperty(
                        error_code=403,
                        response_code=200,
                        response_page_path="/index.html",
                        error_caching_min_ttl=0,
                    ),
                    cf.CfnDistribution.CustomErrorResponseProperty(
                        error_code=404,
                        response_code=200,
                        response_page_path="/index.html",
                        error_caching_min_ttl=0,
                    ),
                ],

                # ── Viewer certificate (CloudFront default) ───────────────
                viewer_certificate=cf.CfnDistribution.ViewerCertificateProperty(
                    cloud_front_default_certificate=True,
                ),
            ),
        )

        # ----------------------------------------------------------------
        # S3 Bucket Policy — allow CloudFront OAC to read /ui/* objects
        # ----------------------------------------------------------------
        configs_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowCloudFrontOAC",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
                actions=["s3:GetObject"],
                resources=[f"{configs_bucket.bucket_arn}/ui/*"],
                conditions={
                    "StringEquals": {
                        "AWS:SourceArn": (
                            f"arn:aws:cloudfront::{account}:distribution/"
                            f"{self.distribution.ref}"
                        ),
                    }
                },
            )
        )

        # ----------------------------------------------------------------
        # Outputs
        # ----------------------------------------------------------------
        self.ui_url = f"https://{self.distribution.attr_domain_name}"

        CfnOutput(
            self,
            "SfcControlPlaneUiUrl",
            value=self.ui_url,
            description="SFC Control Plane UI — CloudFront URL",
        )