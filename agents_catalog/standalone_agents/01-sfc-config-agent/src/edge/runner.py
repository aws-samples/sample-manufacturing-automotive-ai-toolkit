#!/usr/bin/env python3
"""
WP-11 — aws-sfc-runtime-agent (runner.py)

Edge agent that:
  1. Bootstraps SFC binary (downloads from GitHub if needed) and Java
  2. Vends AWS credentials via IoT mTLS role alias
  3. Launches SFC as a subprocess with captured stdout/stderr
  4. Ships OTEL log records to CloudWatch
  5. Maintains an MQTT5 control channel (telemetry, diagnostics, config-update, restart)
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
_telemetry_enabled = True
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
    return sfc_config.get("$sfc-version", "1.7.1")


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


def _download_sfc_binaries(version: str, sfc_bin_dir: Path) -> Path:
    """Download SFC release jar from GitHub and return path to executable."""
    sfc_bin_dir.mkdir(parents=True, exist_ok=True)
    jar_name = f"sfc-{version}-all.jar"
    jar_path = sfc_bin_dir / jar_name
    if jar_path.exists():
        logger.info("SFC jar already present: %s", jar_path)
        return jar_path
    url = (
        f"https://github.com/aws-samples/shopfloor-connectivity/releases/download/"
        f"v{version}/{jar_name}"
    )
    logger.info("Downloading SFC %s from %s …", version, url)
    urllib.request.urlretrieve(url, jar_path)
    logger.info("Downloaded SFC jar: %s", jar_path)
    return jar_path


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

def _start_sfc(java_bin: str, jar_path: Path, sfc_config_path: Path) -> subprocess.Popen:
    env = {**os.environ}
    with _credentials_lock:
        env.update(_aws_credentials)
    cmd = [java_bin, "-jar", str(jar_path), "-config", str(sfc_config_path)]
    logger.info("Launching SFC: %s", " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
        bufsize=1,
    )
    return proc


def _capture_sfc_output(proc: subprocess.Popen, no_otel: bool) -> None:
    """Read SFC stdout line-by-line; update ring buffer; ship to OTEL."""
    global _sfc_running
    _sfc_running.set()
    try:
        for line in proc.stdout:  # type: ignore[union-attr]
            line = line.rstrip()
            with _recent_logs_lock:
                _recent_logs.append(line)
            if no_otel:
                print(line, flush=True)
            else:
                _emit_otel_log(line)
    except Exception as exc:
        logger.warning("SFC output capture ended: %s", exc)
    finally:
        _sfc_running.clear()
        logger.info("SFC process output stream ended (pid=%s)", proc.pid)
        # Publish final heartbeat with sfcRunning=false
        _publish_heartbeat_now(iot_cfg=None, sfc_pid=proc.pid, running=False)


def _restart_sfc(java_bin: str, jar_path: Path, sfc_config_path: Path) -> None:
    global _sfc_proc
    if _sfc_proc and _sfc_proc.poll() is None:
        logger.info("Terminating existing SFC process (pid=%s) for restart …", _sfc_proc.pid)
        _sfc_proc.terminate()
        try:
            _sfc_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _sfc_proc.kill()
    _sfc_proc = _start_sfc(java_bin, jar_path, sfc_config_path)
    t = threading.Thread(
        target=_capture_sfc_output,
        args=(_sfc_proc, False),
        daemon=True,
        name="sfc-output",
    )
    t.start()
    logger.info("SFC restarted with pid=%s", _sfc_proc.pid)


# ─────────────────────────────────────────────────────────────────────────────
# 4. OTEL log shipping
# ─────────────────────────────────────────────────────────────────────────────

def _init_otel(iot_cfg: dict) -> bool:
    """Initialise OTEL SDK targeting CloudWatch OTLP endpoint. Returns True on success."""
    global _otel_processor, _logger_provider
    try:
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.sdk._logs import LoggerProvider
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.sdk.resources import Resource

        region = iot_cfg.get("region", "us-east-1")
        log_group = iot_cfg.get("logGroupName", f"/sfc/launch-packages/{iot_cfg['packageId']}")
        endpoint = f"https://logs.{region}.amazonaws.com/v1/logs"

        exporter = OTLPLogExporter(
            endpoint=endpoint,
            headers={"x-aws-log-group": log_group},
        )
        processor = BatchLogRecordProcessor(exporter)
        resource = Resource.create({
            "service.name": "aws-sfc-runtime-agent",
            "sfc.package_id": iot_cfg.get("packageId", ""),
        })
        provider = LoggerProvider(resource=resource)
        provider.add_log_record_processor(processor)
        set_logger_provider(provider)
        _otel_processor = processor
        _logger_provider = provider
        logger.info("OTEL initialised → %s", endpoint)
        return True
    except ImportError as exc:
        logger.warning("OTEL SDK not available (%s); logs will not be shipped", exc)
        return False


def _emit_otel_log(line: str) -> None:
    global _telemetry_enabled
    if not _telemetry_enabled or not _logger_provider:
        return
    try:
        from opentelemetry._logs import get_logger
        from opentelemetry._logs.severity import SeverityNumber
        otel_logger = get_logger("sfc-subprocess")
        upper = line.upper()
        if "ERROR" in upper:
            sev_text, sev_num = "ERROR", SeverityNumber.ERROR
        elif "WARN" in upper:
            sev_text, sev_num = "WARN", SeverityNumber.WARN
        elif "DEBUG" in upper:
            sev_text, sev_num = "DEBUG", SeverityNumber.DEBUG
        else:
            sev_text, sev_num = "INFO", SeverityNumber.INFO
        from opentelemetry.sdk._logs import LogRecord
        from opentelemetry.util.types import Attributes
        record = LogRecord(
            timestamp=int(time.time_ns()),
            observed_timestamp=int(time.time_ns()),
            severity_text=sev_text,
            severity_number=sev_num,
            body=line,
            resource=_logger_provider.resource,
        )
        otel_logger.emit(record)
    except Exception as exc:
        logger.debug("OTEL emit failed: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# 5. MQTT5 control channel
# ─────────────────────────────────────────────────────────────────────────────

def _connect_mqtt(iot_cfg: dict):
    """Connect to IoT broker via mTLS and subscribe to control topics."""
    global _mqtt_connection
    try:
        from awsiot import mqtt5_client, mqtt_connection_builder

        endpoint = iot_cfg["iotEndpoint"].replace(
            "credentials.", ""
        ).replace("/role-aliases", "")
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
            qos=mqtt5_client.QoS.AT_LEAST_ONCE,
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
    global _telemetry_enabled, _diagnostics_enabled, _sfc_proc
    try:
        msg = json.loads(payload)
        suffix = topic.split("/")[-1]
        logger.info("Control message received: topic=%s payload=%s", topic, msg)

        if suffix == "telemetry":
            _telemetry_enabled = bool(msg.get("enabled", True))
            if not _telemetry_enabled and _otel_processor:
                pass  # processor remains; we gate at emit time
            logger.info("Telemetry set to %s", _telemetry_enabled)

        elif suffix == "diagnostics":
            _diagnostics_enabled = bool(msg.get("enabled", False))
            level = logging.DEBUG if _diagnostics_enabled else logging.WARNING
            logging.getLogger("sfc-subprocess").setLevel(level)
            logger.info("Diagnostics set to %s", _diagnostics_enabled)

        elif suffix == "config-update":
            presigned_url = msg.get("presignedUrl")
            if presigned_url:
                _apply_config_update(presigned_url, iot_cfg)

        elif suffix == "restart":
            if msg.get("restart"):
                logger.info("Restart command received")
                sfc_bin_dir = _HERE / ".sfc-bin"
                sfc_version = _detect_sfc_version(_load_sfc_config())
                jar_path = sfc_bin_dir / f"sfc-{sfc_version}-all.jar"
                java_bin = _ensure_java(sfc_bin_dir)
                _restart_sfc(java_bin, jar_path, _SFC_CONFIG_PATH)

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
        jar_path = sfc_bin_dir / f"sfc-{sfc_version}-all.jar"
        java_bin = _ensure_java(sfc_bin_dir)
        _restart_sfc(java_bin, jar_path, _SFC_CONFIG_PATH)
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
        "telemetryEnabled": _telemetry_enabled,
        "diagnosticsEnabled": _diagnostics_enabled,
        "recentLogs": recent,
    })
    topic = f"sfc/{cfg['packageId']}/heartbeat"
    try:
        from awsiot.mqtt_connection_builder import _MqttConnection
        _mqtt_connection.publish(
            topic=topic,
            payload=payload,
            qos=0,  # QoS 0 for heartbeat (best-effort)
        )
    except Exception as exc:
        logger.debug("Heartbeat publish failed: %s", exc)


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

    # Step 2: Fetch initial credentials
    try:
        creds = _fetch_credentials(iot_cfg)
        with _credentials_lock:
            _aws_credentials.update(creds)
        os.environ.update(creds)
    except Exception as exc:
        logger.error("Initial credential fetch failed: %s", exc)
        sys.exit(1)

    # Step 4: Init OTEL (unless --no-otel)
    if not args.no_otel:
        _init_otel(iot_cfg)

    # Step 1: Ensure Java + SFC binary
    java_bin = _ensure_java(sfc_bin_dir)
    jar_path = _download_sfc_binaries(sfc_version, sfc_bin_dir)

    # Step 3: Start SFC subprocess
    _sfc_proc = _start_sfc(java_bin, jar_path, _SFC_CONFIG_PATH)
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

    # Wait for SFC process (or shutdown signal)
    logger.info("SFC runner active — waiting for shutdown signal or SFC exit")
    while not _shutdown.is_set():
        if _sfc_proc.poll() is not None:
            logger.warning("SFC process exited with code %s", _sfc_proc.returncode)
            break
        time.sleep(1)

    _shutdown.set()


if __name__ == "__main__":
    main()