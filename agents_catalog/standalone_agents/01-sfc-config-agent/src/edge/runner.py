#!/usr/bin/env python3
"""
WP-11 — aws-sfc-runtime-agent (runner.py)

Edge agent that:
  1. Bootstraps SFC binary (downloads from GitHub if needed) and Java
  2. Vends AWS credentials via IoT mTLS role alias
  3. Launches SFC as a subprocess with captured stdout/stderr
  4. Ships OTEL log records to CloudWatch (SigV4-signed)
  5. Maintains an MQTT5 control channel (diagnostics, config-update, restart)
  6. Publishes heartbeat every 5 s on sfc/{packageId}/heartbeat
  7. Refreshes IoT credentials every 50 min
  8. Handles SIGTERM/SIGINT gracefully

Usage:
  uv run runner.py [--no-otel]
"""

from __future__ import annotations

import argparse
import collections
import json
import logging
import os
import platform
import signal
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("sfc-runner")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent.resolve()
_IOT_CONFIG_PATH = _HERE.parent / "iot" / "iot-config.json"
_SFC_CONFIG_PATH = _HERE.parent / "sfc-config.json"
_CERT_PATH = _HERE.parent / "iot" / "device.cert.pem"
_KEY_PATH = _HERE.parent / "iot" / "device.private.key"
_CA_PATH = _HERE.parent / "iot" / "AmazonRootCA1.pem"

_HEARTBEAT_INTERVAL_S = 5
_CREDENTIAL_REFRESH_INTERVAL_S = 50 * 60  # 50 minutes
_RECENT_LOG_RING_SIZE = 3
_CREDENTIAL_ENDPOINT_TEMPLATE = (
    "https://{iotEndpoint}/role-aliases/{roleAlias}/credentials"
)
_GITHUB_RELEASE_BASE = (
    "https://github.com/awslabs/industrial-shopfloor-connect/releases/download/v{version}/{artifact}"
)

# ─────────────────────────────────────────────────────────────────────────────
# Shared state
# ─────────────────────────────────────────────────────────────────────────────
_sfc_proc: subprocess.Popen | None = None
_sfc_running = threading.Event()
_shutdown = threading.Event()
_recent_logs: deque[str] = deque(maxlen=_RECENT_LOG_RING_SIZE)
_recent_logs_lock = threading.Lock()
_aws_credentials: dict[str, str] = {}
_credentials_lock = threading.Lock()
_diagnostics_enabled = False
_otel_processor = None   # set after OTEL init
_logger_provider = None  # set after OTEL init
_mqtt_connection = None  # set after MQTT connect


# ─────────────────────────────────────────────────────────────────────────────
# 1. Bootstrap helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_iot_config() -> dict:
    with open(_IOT_CONFIG_PATH) as fh:
        return json.load(fh)


def _load_sfc_config() -> dict:
    with open(_SFC_CONFIG_PATH) as fh:
        return json.load(fh)


def _detect_sfc_version(sfc_config: dict) -> str:
    return sfc_config.get("$sfc-version", "1.10.8")


def _detect_sfc_modules(sfc_config: dict) -> list[str]:
    """
    Parse AdapterTypes and TargetTypes JarFiles entries to derive module names.

    Each JarFiles entry follows the pattern: ${MODULES_DIR}/{module-name}/lib
    The middle path segment is the module tar.gz name (without .tar.gz).

    Returns a deduplicated list of module names, e.g. ['simulator', 'debug-target'].
    """
    modules: set[str] = set()
    for section_key in ("AdapterTypes", "TargetTypes"):
        for _type_name, type_cfg in sfc_config.get(section_key, {}).items():
            for jar_path in type_cfg.get("JarFiles", []):
                # Normalise: replace backslashes, split on '/'
                parts = jar_path.replace("\\", "/").split("/")
                # Pattern: ['${MODULES_DIR}', '{module}', 'lib']
                # Find the part after ${MODULES_DIR}
                try:
                    idx = next(i for i, p in enumerate(parts) if "MODULES_DIR" in p)
                    module_name = parts[idx + 1]
                    if module_name:
                        modules.add(module_name)
                except (StopIteration, IndexError):
                    logger.warning("Could not parse module name from JarFiles entry: %s", jar_path)
    return sorted(modules)


def _ensure_java(sfc_bin_dir: Path) -> str:
    """Return path to java binary; install Temurin JRE via Adoptium API if absent."""
    java = "java"
    try:
        subprocess.run([java, "-version"], capture_output=True, check=True)
        return java
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    logger.info("Java not found — downloading Temurin 21 via Adoptium API …")
    arch = "x64" if platform.machine() in ("x86_64", "AMD64") else "aarch64"
    url = (
        f"https://api.adoptium.net/v3/binary/latest/21/ga/"
        f"linux/{arch}/jre/hotspot/normal/eclipse"
    )
    dest = sfc_bin_dir / "jre.tar.gz"
    urllib.request.urlretrieve(url, dest)
    subprocess.run(["tar", "-xzf", str(dest), "-C", str(sfc_bin_dir)], check=True)
    # Find extracted directory
    for entry in sfc_bin_dir.iterdir():
        java_bin = entry / "bin" / "java"
        if java_bin.exists():
            logger.info("Java installed at %s", java_bin)
            return str(java_bin)
    raise RuntimeError("Java extraction failed — java binary not found")


def _download_and_extract(artifact: str, version: str, sfc_bin_dir: Path) -> None:
    """
    Download {artifact}.tar.gz from the SFC GitHub release and extract into sfc_bin_dir.
    Skips if the artifact directory already exists (idempotent).
    """
    extract_marker = sfc_bin_dir / artifact
    if extract_marker.exists():
        logger.info("SFC artifact already present: %s", extract_marker)
        return

    url = _GITHUB_RELEASE_BASE.format(version=version, artifact=f"{artifact}.tar.gz")
    dest = sfc_bin_dir / f"{artifact}.tar.gz"
    logger.info("Downloading SFC artifact %s from %s …", artifact, url)
    try:
        urllib.request.urlretrieve(url, dest)
    except Exception as exc:
        raise RuntimeError(f"Failed to download {artifact}.tar.gz: {exc}") from exc

    logger.info("Extracting %s …", dest)
    try:
        with tarfile.open(dest, "r:gz") as tf:
            tf.extractall(path=sfc_bin_dir)
    except Exception as exc:
        raise RuntimeError(f"Failed to extract {dest}: {exc}") from exc
    finally:
        # Remove the archive after extraction regardless of outcome
        try:
            dest.unlink(missing_ok=True)
        except Exception:
            pass

    logger.info("SFC artifact %s ready at %s", artifact, extract_marker)


def _ensure_sfc_artifacts(version: str, sfc_cfg: dict, sfc_bin_dir: Path) -> Path:
    """
    Ensure all required SFC artifacts are downloaded and extracted.

    Always downloads sfc-main.  Additionally downloads every module referenced
    in AdapterTypes / TargetTypes JarFiles entries.

    Returns the path to the sfc-main launcher jar.
    """
    sfc_bin_dir.mkdir(parents=True, exist_ok=True)

    # 1. Always ensure sfc-main
    _download_and_extract("sfc-main", version, sfc_bin_dir)

    # 2. Derive and ensure module artifacts from sfc-config
    modules = _detect_sfc_modules(sfc_cfg)
    logger.info("SFC modules required by config: %s", modules)
    for module in modules:
        _download_and_extract(module, version, sfc_bin_dir)

    # 3. Locate the sfc-main binary
    sfc_binary = sfc_bin_dir / "sfc-main" / "bin" / "sfc-main"
    if not sfc_binary.exists():
        raise RuntimeError(
            f"SFC binary not found at {sfc_binary}. "
            "Check the extracted sfc-main artifact structure."
        )
    sfc_binary.chmod(sfc_binary.stat().st_mode | 0o111)
    logger.info("SFC binary: %s", sfc_binary)
    return sfc_binary


# ─────────────────────────────────────────────────────────────────────────────
# 2. IoT credential vending
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_credentials(iot_cfg: dict) -> dict:
    """Fetch temporary AWS credentials from IoT credential provider endpoint."""
    url = _CREDENTIAL_ENDPOINT_TEMPLATE.format(
        iotEndpoint=iot_cfg["iotEndpoint"],
        roleAlias=iot_cfg["roleAlias"],
    )
    req = urllib.request.Request(url)
    req.add_header("x-amzn-iot-thingname", iot_cfg["thingName"])
    import ssl
    ctx = ssl.create_default_context()
    ctx.load_cert_chain(certfile=str(_CERT_PATH), keyfile=str(_KEY_PATH))
    ctx.load_verify_locations(cafile=str(_CA_PATH))
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        data = json.loads(resp.read())
    creds = data["credentials"]
    logger.info(
        "Fetched credentials, expiration: %s",
        creds.get("expiration", "unknown"),
    )
    return {
        "AWS_ACCESS_KEY_ID": creds["accessKeyId"],
        "AWS_SECRET_ACCESS_KEY": creds["secretAccessKey"],
        "AWS_SESSION_TOKEN": creds["sessionToken"],
        "AWS_REGION": iot_cfg.get("region", os.environ.get("AWS_REGION", "us-east-1")),
    }


def _credential_refresh_loop(iot_cfg: dict) -> None:
    """Background thread: re-fetch credentials every 50 min."""
    global _aws_credentials
    while not _shutdown.is_set():
        try:
            creds = _fetch_credentials(iot_cfg)
            with _credentials_lock:
                _aws_credentials = creds
                os.environ.update(creds)
                if _sfc_proc and _sfc_proc.poll() is None:
                    for k, v in creds.items():
                        _sfc_proc.env = getattr(_sfc_proc, "env", os.environ.copy())
                        _sfc_proc.env[k] = v
            logger.info("Credentials refreshed successfully")
        except Exception as exc:
            logger.error("Credential refresh failed: %s", exc)
        _shutdown.wait(timeout=_CREDENTIAL_REFRESH_INTERVAL_S)


# ─────────────────────────────────────────────────────────────────────────────
# 3. SFC subprocess
# ─────────────────────────────────────────────────────────────────────────────

def _start_sfc(
    sfc_binary: Path,
    sfc_config_path: Path,
    sfc_bin_dir: Path,
    log_level_flag: str = "-info",
) -> subprocess.Popen:
    env = {**os.environ}
    with _credentials_lock:
        env.update(_aws_credentials)
    # MODULES_DIR must resolve ${MODULES_DIR} references in sfc-config JarFiles
    env["MODULES_DIR"] = str(sfc_bin_dir)
    cmd = [str(sfc_binary), "-config", str(sfc_config_path), log_level_flag]
    logger.info("Launching SFC: %s", " ".join(cmd))
    logger.info("MODULES_DIR=%s", env["MODULES_DIR"])
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
        bufsize=1,
    )
    return proc


def _capture_stream(stream, no_otel: bool) -> None:
    """Drain one stream (stdout or stderr) line-by-line; print locally; ship to OTEL."""
    try:
        for line in stream:
            line = line.rstrip()
            with _recent_logs_lock:
                _recent_logs.append(line)
            if not no_otel:
                _emit_otel_log(line)
    except Exception as exc:
        logger.warning("SFC stream capture ended: %s", exc)


def _capture_sfc_output(proc: subprocess.Popen, no_otel: bool) -> None:
    """Read SFC stdout+stderr line-by-line; print locally; ship to OTEL."""
    global _sfc_running
    _sfc_running.set()
    # Drain stderr in a sibling thread so neither stream blocks the other
    stderr_thread = threading.Thread(
        target=_capture_stream,
        args=(proc.stderr, no_otel),
        daemon=True,
        name="sfc-stderr",
    )
    stderr_thread.start()
    try:
        _capture_stream(proc.stdout, no_otel)  # type: ignore[arg-type]
    finally:
        stderr_thread.join(timeout=5)
        _sfc_running.clear()
        logger.info("SFC process output stream ended (pid=%s)", proc.pid)
        # Publish final heartbeat with sfcRunning=false
        _publish_heartbeat_now(iot_cfg=None, sfc_pid=proc.pid, running=False)


def _restart_sfc(
    sfc_binary: Path,
    sfc_config_path: Path,
    sfc_bin_dir: Path,
    log_level_flag: str = "-info",
) -> None:
    global _sfc_proc
    if _sfc_proc and _sfc_proc.poll() is None:
        logger.info("Terminating existing SFC process (pid=%s) for restart …", _sfc_proc.pid)
        _sfc_proc.terminate()
        try:
            _sfc_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _sfc_proc.kill()
    _sfc_proc = _start_sfc(sfc_binary, sfc_config_path, sfc_bin_dir, log_level_flag)
    t = threading.Thread(
        target=_capture_sfc_output,
        args=(_sfc_proc, False),
        daemon=True,
        name="sfc-output",
    )
    t.start()
    logger.info("SFC restarted with pid=%s", _sfc_proc.pid)


# ─────────────────────────────────────────────────────────────────────────────
# 4. OTEL log shipping (SigV4-signed for CloudWatch)
# ─────────────────────────────────────────────────────────────────────────────

class _SigV4OTLPLogExporter:
    """
    Wrapper around OTLPLogExporter that signs every HTTP export request with
    AWS SigV4 using the IoT-vended credentials held in _aws_credentials.

    botocore is a transitive dependency of boto3 (already in pyproject.toml).
    """

    def __init__(self, endpoint: str, headers: dict, region: str):
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        self._region = region
        self._endpoint = endpoint
        self._base_headers = headers
        self._exporter = OTLPLogExporter(
            endpoint=endpoint,
            headers=headers,
        )
        # Monkey-patch the session's send to inject SigV4 headers
        self._patch_session()

    def _patch_session(self) -> None:
        """Wrap the underlying requests Session.send to inject SigV4 headers."""
        exporter = self._exporter
        region = self._region
        endpoint = self._endpoint

        # The OTLPLogExporter uses a requests.Session stored at _session
        session = getattr(exporter, "_session", None)
        if session is None:
            logger.warning("Could not locate OTLPLogExporter._session; SigV4 signing disabled")
            return

        original_send = session.send

        def _signed_send(prepared_request, **kwargs):
            try:
                import botocore.auth
                import botocore.awsrequest
                import botocore.credentials
                with _credentials_lock:
                    creds = dict(_aws_credentials)
                if creds:
                    bc_creds = botocore.credentials.Credentials(
                        access_key=creds["AWS_ACCESS_KEY_ID"],
                        secret_key=creds["AWS_SECRET_ACCESS_KEY"],
                        token=creds.get("AWS_SESSION_TOKEN"),
                    )
                    aws_req = botocore.awsrequest.AWSRequest(
                        method=prepared_request.method,
                        url=prepared_request.url,
                        data=prepared_request.body,
                        headers=dict(prepared_request.headers),
                    )
                    signer = botocore.auth.SigV4Auth(bc_creds, "logs", region)
                    signer.add_auth(aws_req)
                    # Inject signed headers back into the prepared request
                    for key, value in aws_req.headers.items():
                        prepared_request.headers[key] = value
            except Exception as exc:
                logger.debug("SigV4 signing failed: %s", exc)
            return original_send(prepared_request, **kwargs)

        session.send = _signed_send
        logger.debug("SigV4 signing patch applied to OTLPLogExporter session")

    # Delegate all OTLPLogExporter interface methods
    def export(self, batch):
        return self._exporter.export(batch)

    def shutdown(self):
        return self._exporter.shutdown()

    def force_flush(self, timeout_millis=30000):
        return self._exporter.force_flush(timeout_millis)


def _ensure_cloudwatch_log_stream(region: str, log_group: str, log_stream: str) -> None:
    """Create the CloudWatch log stream if it does not already exist."""
    import boto3
    from botocore.exceptions import ClientError
    client = boto3.client("logs", region_name=region)
    try:
        client.create_log_stream(logGroupName=log_group, logStreamName=log_stream)
        logger.info("Created CloudWatch log stream: %s in %s", log_stream, log_group)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ResourceAlreadyExistsException":
            logger.debug("CloudWatch log stream already exists: %s", log_stream)
        else:
            logger.warning("Could not create log stream %s: %s", log_stream, exc)


def _init_otel(iot_cfg: dict) -> bool:
    """Initialise OTEL SDK targeting CloudWatch OTLP endpoint. Returns True on success."""
    global _otel_processor, _logger_provider
    try:
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk.resources import Resource

        region = iot_cfg.get("region", "us-east-1")
        log_group = iot_cfg.get("logGroupName", f"/sfc/launch-packages/{iot_cfg['packageId']}")
        endpoint = f"https://logs.{region}.amazonaws.com/v1/logs"

        log_stream = iot_cfg.get("thingName", iot_cfg.get("packageId", "sfc-agent"))
        # Ensure the log stream exists before sending any records
        _ensure_cloudwatch_log_stream(region, log_group, log_stream)
        # Use SigV4-signing wrapper around OTLPLogExporter
        sig_exporter = _SigV4OTLPLogExporter(
            endpoint=endpoint,
            headers={
                "x-aws-log-group": log_group,
                "x-aws-log-stream": log_stream,
            },
            region=region,
        )
        processor = BatchLogRecordProcessor(
            sig_exporter,
            schedule_delay_millis=30_000,  # flush every 30 s (12× less than 5 s default)
        )
        resource = Resource.create({
            "service.name": "aws-sfc-runtime-agent",
            "sfc.package_id": iot_cfg.get("packageId", ""),
        })
        provider = LoggerProvider(resource=resource)
        provider.add_log_record_processor(processor)
        set_logger_provider(provider)
        _otel_processor = processor
        _logger_provider = provider

        # Bridge Python root logger → OTEL so runner.py's own log lines are shipped
        otel_handler = LoggingHandler(level=logging.DEBUG, logger_provider=provider)
        logging.getLogger().addHandler(otel_handler)

        logger.info(
            "OTEL initialised → %s (log-group: %s, log-stream: %s)",
            endpoint, log_group, log_stream,
        )
        return True
    except ImportError as exc:
        logger.warning("OTEL SDK not available (%s); logs will not be shipped", exc)
        return False
    except Exception as exc:
        logger.error("OTEL init failed: %s", exc)
        return False


def _emit_otel_log(line: str) -> None:
    """
    Forward a raw SFC subprocess output line to CloudWatch via the Python
    logging → OTEL bridge installed by _init_otel().

    Severity is inferred by keyword scan; all plain/no-prefix lines default to INFO.
    Exceptions are surfaced at WARNING so they are not silently swallowed.
    """
    if not _logger_provider:
        return
    try:
        sub_logger = logging.getLogger("sfc-subprocess")
        upper = line.upper()
        if "ERROR" in upper:
            sub_logger.error(line)
        elif "WARN" in upper:
            sub_logger.warning(line)
        elif "DEBUG" in upper:
            sub_logger.debug(line)
        else:
            sub_logger.info(line)
    except Exception as exc:
        logger.warning("OTEL emit failed: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# 5. MQTT5 control channel
# ─────────────────────────────────────────────────────────────────────────────

def _connect_mqtt(iot_cfg: dict):
    """Connect to IoT broker via mTLS and subscribe to control topics."""
    global _mqtt_connection
    try:
        from awsiot import mqtt_connection_builder
        from awscrt.mqtt import QoS as MqttQoS

        # Use data endpoint if it looks like a credentials endpoint
        if "credentials.iot" in iot_cfg["iotEndpoint"]:
            import boto3
            data_ep = boto3.client("iot", region_name=iot_cfg["region"]).describe_endpoint(
                endpointType="iot:Data-ATS"
            )["endpointAddress"]
        else:
            data_ep = iot_cfg["iotEndpoint"]

        conn = mqtt_connection_builder.mtls_from_path(
            endpoint=data_ep,
            cert_filepath=str(_CERT_PATH),
            pri_key_filepath=str(_KEY_PATH),
            ca_filepath=str(_CA_PATH),
            client_id=iot_cfg["thingName"],
            clean_session=False,
            keep_alive_secs=30,
        )
        connect_future = conn.connect()
        connect_future.result(timeout=15)
        _mqtt_connection = conn

        topic_prefix = iot_cfg.get("topicPrefix", f"sfc/{iot_cfg['packageId']}/control")
        subscribe_future, _ = conn.subscribe(
            topic=f"{topic_prefix}/#",
            qos=MqttQoS.AT_LEAST_ONCE,
            callback=lambda topic, payload, **_: _dispatch_control(
                topic, payload, iot_cfg
            ),
        )
        subscribe_future.result(timeout=10)
        logger.info("MQTT connected and subscribed to %s/#", topic_prefix)
        return conn
    except Exception as exc:
        logger.error("MQTT connection failed: %s", exc)
        return None


def _dispatch_control(topic: str, payload: bytes, iot_cfg: dict) -> None:
    """Route incoming MQTT control messages to handlers."""
    global _diagnostics_enabled, _sfc_proc
    try:
        msg = json.loads(payload)
        suffix = topic.split("/")[-1]
        logger.info("Control message received: topic=%s payload=%s", topic, msg)

        if suffix == "diagnostics":
            _diagnostics_enabled = bool(msg.get("enabled", False))
            level = logging.DEBUG if _diagnostics_enabled else logging.WARNING
            logging.getLogger("sfc-subprocess").setLevel(level)
            log_flag = "-trace" if _diagnostics_enabled else "-info"
            logger.info(
                "Diagnostics set to %s — restarting SFC with %s",
                _diagnostics_enabled, log_flag,
            )
            sfc_bin_dir = _HERE / ".sfc-bin"
            sfc_cfg = _load_sfc_config()
            sfc_version = _detect_sfc_version(sfc_cfg)
            sfc_binary = _ensure_sfc_artifacts(sfc_version, sfc_cfg, sfc_bin_dir)
            _restart_sfc(sfc_binary, _SFC_CONFIG_PATH, sfc_bin_dir, log_flag)

        elif suffix == "config-update":
            presigned_url = msg.get("presignedUrl")
            if presigned_url:
                _apply_config_update(presigned_url, iot_cfg)

        elif suffix == "restart":
            if msg.get("restart"):
                # logLevel is set by the Lambda based on the persisted
                # diagnosticsEnabled flag; fall back to _diagnostics_enabled
                # for any older messages that don't include it.
                log_flag = msg.get("logLevel") or ("-trace" if _diagnostics_enabled else "-info")
                logger.info("Restart command received — log level: %s", log_flag)
                sfc_bin_dir = _HERE / ".sfc-bin"
                sfc_cfg = _load_sfc_config()
                sfc_version = _detect_sfc_version(sfc_cfg)
                sfc_binary = _ensure_sfc_artifacts(sfc_version, sfc_cfg, sfc_bin_dir)
                _restart_sfc(sfc_binary, _SFC_CONFIG_PATH, sfc_bin_dir, log_flag)

    except Exception as exc:
        logger.error("Control dispatch error: %s", exc)


def _apply_config_update(presigned_url: str, iot_cfg: dict) -> None:
    """Download new sfc-config.json, overwrite local file, restart SFC."""
    try:
        with urllib.request.urlopen(presigned_url, timeout=30) as resp:
            new_config = json.loads(resp.read())
        with open(_SFC_CONFIG_PATH, "w") as fh:
            json.dump(new_config, fh, indent=2)
        logger.info("Config updated from presigned URL; restarting SFC …")
        sfc_version = _detect_sfc_version(new_config)
        sfc_bin_dir = _HERE / ".sfc-bin"
        sfc_binary = _ensure_sfc_artifacts(sfc_version, new_config, sfc_bin_dir)
        # Preserve current diagnostics log level across config-push restarts
        log_flag = "-trace" if _diagnostics_enabled else "-info"
        _restart_sfc(sfc_binary, _SFC_CONFIG_PATH, sfc_bin_dir, log_flag)
    except Exception as exc:
        logger.error("Config update failed: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Heartbeat publisher
# ─────────────────────────────────────────────────────────────────────────────

_heartbeat_iot_cfg: dict | None = None


def _publish_heartbeat_now(iot_cfg: dict | None, sfc_pid: int | None = None, running: bool | None = None) -> None:
    global _mqtt_connection, _heartbeat_iot_cfg
    cfg = iot_cfg or _heartbeat_iot_cfg
    if not cfg or not _mqtt_connection:
        return
    sfc_is_running = running if running is not None else _sfc_running.is_set()
    pid = sfc_pid or (_sfc_proc.pid if _sfc_proc else None)
    with _recent_logs_lock:
        recent = list(_recent_logs)
    payload = json.dumps({
        "packageId": cfg["packageId"],
        "createdAt": cfg.get("createdAt", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sfcPid": pid,
        "sfcRunning": sfc_is_running,
        "diagnosticsEnabled": _diagnostics_enabled,
        "recentLogs": recent,
    })
    topic = f"sfc/{cfg['packageId']}/heartbeat"
    try:
        from awscrt.mqtt import QoS as MqttQoS
        _mqtt_connection.publish(
            topic=topic,
            payload=payload,
            qos=MqttQoS.AT_MOST_ONCE,  # QoS 0 for heartbeat (best-effort)
        )
    except Exception as exc:
        logger.warning("Heartbeat publish failed: %s", exc)


def _heartbeat_loop(iot_cfg: dict) -> None:
    global _heartbeat_iot_cfg
    _heartbeat_iot_cfg = iot_cfg
    while not _shutdown.is_set():
        _publish_heartbeat_now(iot_cfg)
        _shutdown.wait(timeout=_HEARTBEAT_INTERVAL_S)


# ─────────────────────────────────────────────────────────────────────────────
# 8. Graceful shutdown
# ─────────────────────────────────────────────────────────────────────────────

def _shutdown_handler(signum, frame) -> None:
    logger.info("Shutdown signal received (sig=%s); stopping …", signum)
    _shutdown.set()

    # Publish final heartbeat
    _publish_heartbeat_now(iot_cfg=None, running=False)

    # Flush OTEL
    if _logger_provider:
        try:
            _logger_provider.force_flush(timeout_millis=5000)
            _logger_provider.shutdown()
        except Exception:
            pass

    # Disconnect MQTT
    if _mqtt_connection:
        try:
            _mqtt_connection.disconnect().result(timeout=5)
        except Exception:
            pass

    # Terminate SFC subprocess
    if _sfc_proc and _sfc_proc.poll() is None:
        logger.info("Terminating SFC subprocess (pid=%s) …", _sfc_proc.pid)
        _sfc_proc.terminate()
        try:
            _sfc_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _sfc_proc.kill()

    logger.info("Shutdown complete")
    sys.exit(0)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    global _sfc_proc

    parser = argparse.ArgumentParser(description="aws-sfc-runtime-agent")
    parser.add_argument("--no-otel", action="store_true", help="Disable OTEL CloudWatch delivery")
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGINT, _shutdown_handler)

    # Load configuration
    iot_cfg = _load_iot_config()
    sfc_cfg = _load_sfc_config()
    sfc_version = _detect_sfc_version(sfc_cfg)
    sfc_bin_dir = _HERE / ".sfc-bin"

    logger.info(
        "SFC Runtime Agent starting — package=%s config=%s sfc-version=%s",
        iot_cfg.get("packageId"),
        iot_cfg.get("configId"),
        sfc_version,
    )

    # Step 2: Fetch initial credentials (must happen before OTEL so SigV4 signing works)
    try:
        creds = _fetch_credentials(iot_cfg)
        with _credentials_lock:
            _aws_credentials.update(creds)
        os.environ.update(creds)
    except Exception as exc:
        logger.error("Initial credential fetch failed: %s", exc)
        sys.exit(1)

    # Step 4: Init OTEL (unless --no-otel) — after credentials are available
    if not args.no_otel:
        _init_otel(iot_cfg)

    # Step 1: Ensure SFC artifacts (sfc-main binary + all modules from config)
    sfc_binary = _ensure_sfc_artifacts(sfc_version, sfc_cfg, sfc_bin_dir)

    # Step 3: Start SFC subprocess
    _sfc_proc = _start_sfc(sfc_binary, _SFC_CONFIG_PATH, sfc_bin_dir)
    output_thread = threading.Thread(
        target=_capture_sfc_output,
        args=(_sfc_proc, args.no_otel),
        daemon=True,
        name="sfc-output",
    )
    output_thread.start()

    # Step 5: Connect MQTT control channel
    _connect_mqtt(iot_cfg)

    # Step 6: Start heartbeat publisher
    hb_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(iot_cfg,),
        daemon=True,
        name="heartbeat",
    )
    hb_thread.start()

    # Step 7: Start credential refresh thread
    cred_thread = threading.Thread(
        target=_credential_refresh_loop,
        args=(iot_cfg,),
        daemon=True,
        name="cred-refresh",
    )
    cred_thread.start()

    # Wait for shutdown signal — SFC subprocess exit does NOT stop the runner
    logger.info("SFC runner active — waiting for shutdown signal")
    while not _shutdown.is_set():
        if _sfc_proc is not None and _sfc_proc.poll() is not None:
            logger.warning(
                "SFC process exited with code %s; runner continues",
                _sfc_proc.returncode,
            )
            _sfc_proc = None  # clear so heartbeat reports sfcRunning=false
        time.sleep(1)

    _shutdown.set()
    # Drain any buffered OTEL records (e.g. SFC subprocess stdout captured before exit)
    if _logger_provider:
        try:
            _logger_provider.force_flush(timeout_millis=5000)
        except Exception:
            pass


if __name__ == "__main__":
    main()
