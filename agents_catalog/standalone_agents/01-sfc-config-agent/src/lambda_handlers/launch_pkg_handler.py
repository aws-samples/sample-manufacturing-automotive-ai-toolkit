"""WP-06 — fn-launch-pkg: Launch package assembly + list/get/delete/download."""

from __future__ import annotations
import io, json, logging, os, uuid, zipfile
from datetime import datetime, timezone
import boto3 #requests
from sfc_cp_utils import ddb as ddb_util, s3 as s3_util, iot as iot_util

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
                return _delete_package(package_id)
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

    # Load SFC config
    cfg_item = ddb_util.get_config(_cfg_table, config_id, config_version)
    if not cfg_item:
        return _error(404, "NOT_FOUND", f"Config {config_id}/{config_version} not found")
    s3_key = cfg_item.get("s3Key") or s3_util.config_s3_key(config_id, cfg_item["version"])
    sfc_config = s3_util.get_config_json(CONFIGS_BUCKET, s3_key)
    config_version = cfg_item["version"]

    package_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

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

    # Upload zip
    zip_key = s3_util.package_zip_s3_key(package_id)
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


def _delete_package(package_id: str) -> dict:
    pkg = ddb_util.get_package(_pkg_table, package_id)
    if not pkg:
        return _error(404, "NOT_FOUND", f"Package {package_id} not found")
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
        #resp = requests.get(_AMAZON_ROOT_CA_URL, timeout=10)
        #resp.raise_for_status()
        return "TBD"
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