"""
sfc_cp_utils.iot — IoT provisioning and credential-endpoint helpers.

provision_thing()  — creates an IoT Thing, key-pair, certificate, IoT policy,
                     role alias, and IAM role scoped to the SFC config targets.
revoke_and_delete_thing() — reverses the above.
derive_iam_policy_statements() — inspects SFC config targets and returns the
                                  minimal IAM policy statements required.
get_iot_credential_endpoint() — returns the IoT credentials endpoint URL.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import boto3

logger = logging.getLogger(__name__)

# Amazon Root CA 1 — bundled so the zip is self-contained.
AMAZON_ROOT_CA_URL = "https://www.amazontrust.com/repository/AmazonRootCA1.pem"

# Permissions boundary managed policy name — must exist in the account.
# Created separately (e.g., in a bootstrap stack or by a platform team).
PERMISSIONS_BOUNDARY_POLICY_NAME = "SfcEdgeRolePermissionsBoundary"


# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────

def provision_thing(package_id: str, region: str, sfc_config: dict | None = None) -> dict:
    """
    Create all IoT and IAM resources required for a Launch Package.

    Returns a dict with:
      thingName, certArn, certPem, privateKey, roleAliasName, roleAliasArn,
      iamRoleArn, iotEndpoint
    """
    iot = boto3.client("iot", region_name=region)
    iam = boto3.client("iam", region_name=region)
    sts = boto3.client("sts", region_name=region)

    account_id = sts.get_caller_identity()["Account"]
    thing_name = f"sfc-{package_id}"
    role_alias_name = f"sfc-role-alias-{package_id}"
    iam_role_name = f"sfc-edge-role-{package_id}"
    iot_policy_name = f"sfc-iot-policy-{package_id}"

    # 1. Create IoT Thing
    iot.create_thing(thingName=thing_name)
    logger.info("Created IoT Thing: %s", thing_name)

    # 2. Create key pair + certificate
    cert_resp = iot.create_keys_and_certificate(setAsActive=True)
    cert_arn = cert_resp["certificateArn"]
    cert_pem = cert_resp["certificatePem"]
    private_key = cert_resp["keyPair"]["PrivateKey"]
    logger.info("Created certificate: %s", cert_arn)

    # 3. Create IoT policy (control channel + heartbeat)
    iot_policy_doc = _build_iot_policy(package_id, region, account_id)
    try:
        iot.create_policy(
            policyName=iot_policy_name,
            policyDocument=json.dumps(iot_policy_doc),
        )
    except iot.exceptions.ResourceAlreadyExistsException:
        pass
    iot.attach_policy(policyName=iot_policy_name, target=cert_arn)
    iot.attach_thing_principal(thingName=thing_name, principal=cert_arn)

    # 4. Create IAM role for edge credential vending
    iam_role_arn = _create_edge_iam_role(
        iam, iam_role_name, package_id, region, account_id, sfc_config
    )
    logger.info("Created IAM role: %s", iam_role_arn)

    # 5. Create IoT Role Alias
    try:
        alias_resp = iot.create_role_alias(
            roleAlias=role_alias_name,
            roleArn=iam_role_arn,
            credentialDurationSeconds=3600,
        )
        role_alias_arn = alias_resp["roleAliasArn"]
    except iot.exceptions.ResourceAlreadyExistsException:
        alias_desc = iot.describe_role_alias(roleAlias=role_alias_name)
        role_alias_arn = alias_desc["roleAliasDescription"]["roleAliasArn"]

    # 6. Resolve IoT credential endpoint
    iot_endpoint = get_iot_credential_endpoint(region)

    # 7. Pre-create CloudWatch log group
    logs = boto3.client("logs", region_name=region)
    log_group_name = f"/sfc/launch-packages/{package_id}"
    try:
        logs.create_log_group(logGroupName=log_group_name)
    except logs.exceptions.ResourceAlreadyExistsException:
        pass

    return {
        "thingName": thing_name,
        "certArn": cert_arn,
        "certPem": cert_pem,
        "privateKey": private_key,
        "roleAliasName": role_alias_name,
        "roleAliasArn": role_alias_arn,
        "iamRoleArn": iam_role_arn,
        "iotEndpoint": iot_endpoint,
        "logGroupName": log_group_name,
    }


def revoke_and_delete_thing(
    thing_name: str,
    cert_arn: str,
    role_alias_name: str,
    iam_role_name: str,
    region: str,
) -> None:
    """
    Revoke (deactivate) and delete all IoT/IAM resources created by provision_thing.
    Silently skips resources that have already been deleted.
    """
    iot = boto3.client("iot", region_name=region)
    iam = boto3.client("iam", region_name=region)

    cert_id = cert_arn.split("/")[-1]
    iot_policy_name = f"sfc-iot-policy-{thing_name.removeprefix('sfc-')}"

    # Detach cert from thing
    _try(lambda: iot.detach_thing_principal(thingName=thing_name, principal=cert_arn))
    # Detach IoT policy from cert
    _try(lambda: iot.detach_policy(policyName=iot_policy_name, target=cert_arn))
    # Deactivate + delete cert
    _try(lambda: iot.update_certificate(certificateId=cert_id, newStatus="INACTIVE"))
    _try(lambda: iot.delete_certificate(certificateId=cert_id, forceDelete=True))
    # Delete IoT policy
    _try(lambda: iot.delete_policy(policyName=iot_policy_name))
    # Delete role alias
    _try(lambda: iot.delete_role_alias(roleAlias=role_alias_name))
    # Delete IoT thing
    _try(lambda: iot.delete_thing(thingName=thing_name))
    # Delete IAM role (detach all policies first)
    _delete_iam_role(iam, iam_role_name)

    logger.info("Revoked and deleted IoT/IAM resources for thing: %s", thing_name)


def get_iot_credential_endpoint(region: str) -> str:
    """Return the IoT credential provider endpoint for *region*."""
    iot = boto3.client("iot", region_name=region)
    resp = iot.describe_endpoint(endpointType="iot:CredentialProvider")
    return resp["endpointAddress"]


def get_iot_data_endpoint(region: str) -> str:
    """Return the IoT data endpoint (ATS) for *region*."""
    iot = boto3.client("iot", region_name=region)
    resp = iot.describe_endpoint(endpointType="iot:Data-ATS")
    return resp["endpointAddress"]


def derive_iam_policy_statements(sfc_config: dict, package_id: str, region: str, account_id: str) -> list[dict]:
    """
    Inspect the SFC config *targets* section and return minimal IAM policy
    statements required for the edge device role.
    Always includes the CloudWatch OTEL log statements.
    """
    statements: list[dict] = []
    log_group_arn = f"arn:aws:logs:{region}:{account_id}:log-group:/sfc/launch-packages/{package_id}*"

    # CloudWatch OTEL (always required)
    statements.append({
        "Effect": "Allow",
        "Action": [
            "logs:CreateLogGroup",
            "logs:CreateLogDelivery",
            "logs:PutLogEvents",
            "logs:DescribeLogStreams",
            "logs:CreateLogStream",
        ],
        "Resource": log_group_arn,
    })

    targets = sfc_config.get("Targets", {})
    if isinstance(targets, list):
        targets = {t.get("Name", str(i)): t for i, t in enumerate(targets)}

    for _name, target in targets.items():
        target_type = target.get("TargetType") or target.get("Type") or ""
        if "IoTSiteWise" in target_type or "AwsSiteWise" in target_type:
            statements.append({
                "Effect": "Allow",
                "Action": ["iotsitewise:BatchPutAssetPropertyValue"],
                "Resource": "*",
            })
        elif "Kinesis" in target_type:
            stream_arn = target.get("StreamArn", f"arn:aws:kinesis:{region}:{account_id}:stream/*")
            statements.append({
                "Effect": "Allow",
                "Action": ["kinesis:PutRecord", "kinesis:PutRecords"],
                "Resource": stream_arn,
            })
        elif "S3" in target_type:
            bucket_arn = target.get("BucketArn", f"arn:aws:s3:::*")
            statements.append({
                "Effect": "Allow",
                "Action": ["s3:PutObject"],
                "Resource": f"{bucket_arn}/*",
            })
        elif "IoT" in target_type or "Mqtt" in target_type:
            topic = target.get("TopicName", "*")
            topic_arn = f"arn:aws:iot:{region}:{account_id}:topic/{topic}"
            statements.append({
                "Effect": "Allow",
                "Action": ["iot:Publish"],
                "Resource": topic_arn,
            })

    # IoT credential provider (always required for mTLS credential vending)
    statements.append({
        "Effect": "Allow",
        "Action": ["iot:AssumeRoleWithCertificate"],
        "Resource": f"arn:aws:iot:{region}:{account_id}:rolealias/sfc-role-alias-{package_id}",
    })

    return statements


# ────────────────────────────────────────────────────────────────────────────
# Private helpers
# ────────────────────────────────────────────────────────────────────────────

def _build_iot_policy(package_id: str, region: str, account_id: str) -> dict:
    thing_name = f"sfc-{package_id}"
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "iot:Connect",
                "Resource": f"arn:aws:iot:{region}:{account_id}:client/{thing_name}",
            },
            {
                "Effect": "Allow",
                "Action": "iot:Subscribe",
                "Resource": f"arn:aws:iot:{region}:{account_id}:topicfilter/sfc/{package_id}/control/*",
            },
            {
                "Effect": "Allow",
                "Action": "iot:Receive",
                "Resource": f"arn:aws:iot:{region}:{account_id}:topic/sfc/{package_id}/control/*",
            },
            {
                "Effect": "Allow",
                "Action": "iot:Publish",
                "Resource": f"arn:aws:iot:{region}:{account_id}:topic/sfc/{package_id}/heartbeat",
            },
        ],
    }


def _create_edge_iam_role(
    iam,
    role_name: str,
    package_id: str,
    region: str,
    account_id: str,
    sfc_config: dict | None,
) -> str:
    """Create an IAM role for the edge device and return its ARN."""
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "credentials.iot.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }],
    }

    # Try to resolve permissions boundary ARN
    boundary_arn = f"arn:aws:iam::{account_id}:policy/{PERMISSIONS_BOUNDARY_POLICY_NAME}"

    create_kwargs: dict[str, Any] = {
        "RoleName": role_name,
        "AssumeRolePolicyDocument": json.dumps(trust_policy),
        "Description": f"Edge IAM role for SFC Launch Package {package_id}",
        "Tags": [{"Key": "sfc:packageId", "Value": package_id}],
    }

    # Attach permissions boundary if it exists
    try:
        iam.get_policy(PolicyArn=boundary_arn)
        create_kwargs["PermissionsBoundary"] = boundary_arn
    except Exception:
        logger.warning("Permissions boundary policy %s not found; skipping.", boundary_arn)

    try:
        role_resp = iam.create_role(**create_kwargs)
        role_arn = role_resp["Role"]["Arn"]
    except iam.exceptions.EntityAlreadyExistsException:
        role_arn = iam.get_role(RoleName=role_name)["Role"]["Arn"]
        return role_arn

    # Build and attach inline policy
    statements = derive_iam_policy_statements(
        sfc_config or {}, package_id, region, account_id
    )
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName=f"sfc-edge-policy-{package_id}",
        PolicyDocument=json.dumps({"Version": "2012-10-17", "Statement": statements}),
    )
    return role_arn


def _delete_iam_role(iam, role_name: str) -> None:
    """Detach all managed policies, delete inline policies, then delete the role."""
    try:
        for page in iam.get_paginator("list_attached_role_policies").paginate(RoleName=role_name):
            for policy in page["AttachedPolicies"]:
                _try(lambda: iam.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"]))
        for page in iam.get_paginator("list_role_policies").paginate(RoleName=role_name):
            for pname in page["PolicyNames"]:
                _try(lambda: iam.delete_role_policy(RoleName=role_name, PolicyName=pname))
        iam.delete_role(RoleName=role_name)
    except iam.exceptions.NoSuchEntityException:
        pass


def _try(fn) -> None:
    """Execute *fn*, silently swallowing all exceptions (best-effort cleanup)."""
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Ignored cleanup error: %s", exc)