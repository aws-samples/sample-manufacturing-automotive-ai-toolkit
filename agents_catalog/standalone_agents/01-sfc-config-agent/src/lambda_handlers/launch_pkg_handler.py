"""WP-06 — fn-launch-pkg: Launch package assembly + list/get/delete/download."""

from __future__ import annotations
import io, json, logging, os, uuid, urllib.request, zipfile
from datetime import datetime, timezone
import boto3
from boto3.dynamodb.conditions import Key
from sfc_cp_utils import ddb as ddb_util, s3 as s3_util, iot as iot_util

# SFC_Agent_Files table key helpers (PK=file_type, SK=sort_key)
_FILE_TYPE_CONFIG = "config"

def _config_sort_key(config_id: str, version: str) -> str:
    return f"{config_id}#{version}"

def _ddb_get_config(cfg_table, config_id: str, version: str | None = None) -> dict | None:
    """Fetch a config item using the file_type/sort_key schema of SFC_Agent_Files."""
    if version:
        resp = cfg_table.get_item(
            Key={"file_type": _FILE_TYPE_CONFIG, "sort_key": _config_sort_key(config_id, version)}
        )
        return resp.get("Item")
    resp = cfg_table.query(
        KeyConditionExpression=(
            Key("file_type").eq(_FILE_TYPE_CONFIG)
            & Key("sort_key").begins_with(f"{config_id}#")
        ),
        ScanIndexForward=False,
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else None

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CONFIGS_BUCKET = os.environ["CONFIGS_BUCKET_NAME"]
CONFIG_TABLE_NAME = os.environ["CONFIG_TABLE_NAME"]
LAUNCH_PKG_TABLE = os.environ["LAUNCH_PKG_TABLE_NAME"]
STATE_TABLE_NAME = os.environ["STATE_TABLE_NAME"]
_region = os.environ.get("AWS_REGION", "us-east-1")
_dynamodb = boto3.resource("dynamodb")
_pkg_table = _dynamodb.Table(LAUNCH_PKG_TABLE)
_cfg_table = _dynamodb.Table(CONFIG_TABLE_NAME)
_state_table = _dynamodb.Table(STATE_TABLE_NAME)

# Runner source bundled into the zip
_RUNNER_SRC = os.path.join(os.path.dirname(__file__), "..", "edge", "runner.py")
_EDGE_DIR = os.path.join(os.path.dirname(__file__), "..", "edge")
_AMAZON_ROOT_CA_URL = "https://www.amazontrust.com/repository/AmazonRootCA1.pem"


def handler(event: dict, context) -> dict:
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "")
    path_params = event.get("pathParameters") or {}
    package_id = path_params.get("packageId")
    try:
        if path == "/packages":
            if method == "POST":
                return _create_package(_parse_body(event))
            if method == "GET":
                return _list_packages()
        if package_id and path.endswith("/download"):
            return _get_download_url(package_id)
        if package_id:
            if method == "GET":
                return _get_package(package_id)
            if method == "DELETE":
                deep = (event.get("queryStringParameters") or {}).get("deep", "false").lower() == "true"
                return _delete_package(package_id, deep=deep)
        return _error(404, "NOT_FOUND", "Route not matched")
    except Exception as exc:
        logger.exception("Unhandled error")
        return _error(500, "INTERNAL_ERROR", str(exc))


# ── Route implementations ────────────────────────────────────────────────────

def _create_package(body: dict) -> dict:
    # Resolve config to use
    config_id = body.get("configId")
    config_version = body.get("configVersion")
    if not config_id:
        state = ddb_util.get_control_state(_state_table)
        if not state or not state.get("focusedConfigId"):
            return _error(400, "BAD_REQUEST", "No configId provided and no config in focus")
        config_id = state["focusedConfigId"]
        config_version = config_version or state.get("focusedConfigVersion")

    # Enforce: only the currently focused config/version may create a package
    focused_state = ddb_util.get_control_state(_state_table)
    focused_id = (focused_state or {}).get("focusedConfigId")
    focused_ver = (focused_state or {}).get("focusedConfigVersion")
    if focused_id != config_id or (config_version and focused_ver != config_version):
        return _error(
            400,
            "NOT_FOCUSED",
            f"Only the focused config version can be used to create a launch package. "
            f"Currently focused: {focused_id} @ {focused_ver}",
        )
    # Use the focused version if not explicitly overridden
    if not config_version:
        config_version = focused_ver

    # Load SFC config (using file_type/sort_key schema of SFC_Agent_Files table)
    cfg_item = _ddb_get_config(_cfg_table, config_id, config_version)
    if not cfg_item:
        return _error(404, "NOT_FOUND", f"Config {config_id}/{config_version} not found")
    s3_key = cfg_item.get("s3Key") or s3_util.config_s3_key(config_id, cfg_item["version"])
    sfc_config = s3_util.get_config_json(CONFIGS_BUCKET, s3_key)
    config_version = cfg_item["version"]

    package_id = str(uuid.uuid4())
    now_utc = datetime.now(timezone.utc)
    created_at = now_utc.isoformat()
    # Compact timestamp suffix for the zip file name, e.g. "20260226T160622Z"
    zip_timestamp = now_utc.strftime("%Y%m%dT%H%M%SZ")

    # Write PROVISIONING record
    ddb_util.put_package(_pkg_table, {
        "packageId": package_id, "createdAt": created_at,
        "configId": config_id, "configVersion": config_version,
        "status": "PROVISIONING", "telemetryEnabled": True, "diagnosticsEnabled": False,
    })

    # IoT provisioning
    prov = iot_util.provision_thing(package_id, _region, sfc_config)

    # Rewrite SFC config with IoT credential provider
    rewritten = _inject_iot_credentials(sfc_config, package_id, prov)

    # Build iot-config.json
    iot_config = {
        "iotEndpoint": prov["iotEndpoint"],
        "thingName": prov["thingName"],
        "roleAlias": prov["roleAliasName"],
        "region": _region,
        "logGroupName": prov["logGroupName"],
        "packageId": package_id,
        "configId": config_id,
        "topicPrefix": f"sfc/{package_id}/control",
    }

    # Fetch Amazon Root CA
    root_ca = _fetch_root_ca()

    # Assemble zip in memory
    zip_bytes = _build_zip(package_id, rewritten, iot_config, prov, root_ca)

    # Upload zip (file name includes a timestamp suffix for uniqueness)
    zip_key = s3_util.package_zip_s3_key(package_id, timestamp=zip_timestamp)
    s3_util.put_zip(CONFIGS_BUCKET, zip_key, zip_bytes)

    # Store certs in S3 (private assets — not included in API response)
    s3_util.put_cert_asset(CONFIGS_BUCKET, package_id, "device.cert.pem", prov["certPem"])
    s3_util.put_cert_asset(CONFIGS_BUCKET, package_id, "device.private.key", prov["privateKey"])

    # Update DDB → READY
    ddb_util.update_package(_pkg_table, package_id, created_at, {
        "status": "READY",
        "iotThingName": prov["thingName"],
        "iotCertArn": prov["certArn"],
        "iotRoleAliasArn": prov["roleAliasArn"],
        "iamRoleArn": prov["iamRoleArn"],
        "logGroupName": prov["logGroupName"],
        "s3ZipKey": zip_key,
    })

    download_url = s3_util.generate_presigned_download_url(CONFIGS_BUCKET, zip_key)
    return _ok({"packageId": package_id, "status": "READY", "downloadUrl": download_url})


def _list_packages() -> dict:
    pkgs = ddb_util.list_packages(_pkg_table)
    return _ok({"packages": pkgs})


def _get_package(package_id: str) -> dict:
    pkg = ddb_util.get_package(_pkg_table, package_id)
    if not pkg:
        return _error(404, "NOT_FOUND", f"Package {package_id} not found")
    return _ok(pkg)


def _delete_package(package_id: str, deep: bool = False) -> dict:
    pkg = ddb_util.get_package(_pkg_table, package_id)
    if not pkg:
        return _error(404, "NOT_FOUND", f"Package {package_id} not found")

    if deep:
        # ── Tear down IoT / IAM / CloudWatch resources ────────────────────
        thing_name  = pkg.get("iotThingName", f"sfc-{package_id}")
        cert_arn    = pkg.get("iotCertArn", "")
        role_alias_arn = pkg.get("iotRoleAliasArn", "")
        role_alias_name = role_alias_arn.split("/")[-1] if role_alias_arn else f"sfc-role-alias-{package_id}"
        iam_role_name   = f"sfc-edge-role-{package_id}"

        try:
            iot_util.revoke_and_delete_thing(
                thing_name, cert_arn, role_alias_name, iam_role_name, _region
            )
            logger.info("Deep-deleted IoT/IAM resources for package %s", package_id)
        except Exception as exc:
            logger.warning("Partial failure during deep-delete of %s: %s", package_id, exc)

        # ── Delete CloudWatch log group ───────────────────────────────────
        log_group = pkg.get("logGroupName", f"/sfc/launch-packages/{package_id}")
        try:
            logs_client = boto3.client("logs", region_name=_region)
            logs_client.delete_log_group(logGroupName=log_group)
            logger.info("Deleted log group %s", log_group)
        except Exception as exc:
            logger.warning("Could not delete log group %s: %s", log_group, exc)

    ddb_util.delete_package(_pkg_table, package_id, pkg["createdAt"])
    return {"statusCode": 204, "body": ""}


def _get_download_url(package_id: str) -> dict:
    pkg = ddb_util.get_package(_pkg_table, package_id)
    if not pkg:
        return _error(404, "NOT_FOUND", f"Package {package_id} not found")
    zip_key = pkg.get("s3ZipKey") or s3_util.package_zip_s3_key(package_id)
    url = s3_util.generate_presigned_download_url(CONFIGS_BUCKET, zip_key)
    return _ok({"downloadUrl": url, "expiresIn": 3600})


# ── Helpers ──────────────────────────────────────────────────────────────────

def _inject_iot_credentials(sfc_config: dict, package_id: str, prov: dict) -> dict:
    """Add AwsIotCredentialProviderClients block and patch target credential refs."""
    import copy
    cfg = copy.deepcopy(sfc_config)
    cfg.setdefault("AwsIotCredentialProviderClients", {})[f"CredProvider-{package_id}"] = {
        "IotCredentialEndpoint": prov["iotEndpoint"],
        "RoleAlias": prov["roleAliasName"],
        "ThingName": prov["thingName"],
        "Certificate": "./iot/device.cert.pem",
        "PrivateKey": "./iot/device.private.key",
        "RootCa": "./iot/AmazonRootCA1.pem",
    }
    # Patch all AWS targets to reference the credential provider
    targets = cfg.get("Targets", {})
    if isinstance(targets, dict):
        for tgt in targets.values():
            if isinstance(tgt, dict) and "AwsCredentialClient" not in tgt:
                tgt["AwsCredentialClient"] = f"CredProvider-{package_id}"
    return cfg


def _fetch_root_ca() -> str:
    try:
        req = urllib.request.Request(_AMAZON_ROOT_CA_URL, headers={"User-Agent": "sfc-control-plane/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8")
    except Exception:
        logger.warning("Failed to download Root CA; using placeholder")
        return "# Amazon Root CA 1 — download from https://www.amazontrust.com/repository/AmazonRootCA1.pem\n"


def _read_edge_file(filename: str) -> str:
    path = os.path.join(_EDGE_DIR, filename)
    if os.path.exists(path):
        with open(path) as fh:
            return fh.read()
    return f"# {filename} not found\n"


def _build_zip(package_id: str, sfc_config: dict, iot_config: dict, prov: dict, root_ca: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("sfc-config.json", json.dumps(sfc_config, indent=2))
        zf.writestr("iot/device.cert.pem", prov["certPem"])
        zf.writestr("iot/device.private.key", prov["privateKey"])
        zf.writestr("iot/AmazonRootCA1.pem", root_ca)
        zf.writestr("iot/iot-config.json", json.dumps(iot_config, indent=2))
        zf.writestr("runner/runner.py", _read_edge_file("runner.py"))
        zf.writestr("runner/pyproject.toml", _read_edge_file("pyproject.toml"))
        zf.writestr("runner/.python-version", _read_edge_file(".python-version"))
        zf.writestr("docker/Dockerfile", _read_edge_file("docker/Dockerfile"))
        zf.writestr("docker/docker-build.sh", _read_edge_file("docker/docker-build.sh"))
        zf.writestr("README.md", _build_readme(package_id))
    buf.seek(0)
    return buf.read()


def _build_readme(package_id: str) -> str:
    return f"""# SFC Launch Package — {package_id}

## Quick Start

### Native (uv)
```bash
cd runner
uv sync --frozen
uv run runner.py
```

### Docker
```bash
cd docker
bash docker-build.sh
```

## Contents
- `sfc-config.json` — SFC configuration with IoT credential provider
- `iot/` — Device certificate, private key, Root CA, IoT config
- `runner/` — Python edge agent (runner.py)
- `docker/` — Dockerfile and build script
"""


def _parse_body(event: dict) -> dict:
    return json.loads(event.get("body") or "{}")


def _ok(body): return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body, default=str)}
def _error(s, e, m): return {"statusCode": s, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error": e, "message": m})}