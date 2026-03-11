SFC Agentic Control Plane
=========================

<img src="docs/sfc-control-plane-logo.svg" alt="SFC Control Plane Logo" width="64" height="64" />

## Executive Summary

Connecting industrial equipment to cloud data pipelines is one of manufacturing's most persistent bottlenecks. The **SFC Config Generation Agent** eliminates this barrier by combining a conversational AI assistant with a production-grade cloud control plane. Engineers describe what they need — in plain language or by uploading existing machine specs — and the agent produces a validated, deployment-ready Shop Floor Connectivity (SFC) configuration. That configuration is then packaged, cryptographically credentialed, and pushed to the edge in a single click. If the running process emits errors, a second AI step diagnoses the logs and proposes a corrected configuration automatically.

## Pitch
The SFC Agentic Control Plane eliminates the barrier of onboarding industrial equipment by combining an LLM Agent with a production-grade cloud control plane.

---

## Abstract

This solution wraps [AWS Shop Floor Connectivity (SFC)](https://github.com/awslabs/industrial-shopfloor-connect) — with an AI-driven lifecycle. The **SFC Config Agent** runs as an Amazon Bedrock AgentCore Runtime backed by Claude on Amazon Bedrock. It uses a purpose-built MCP server to validate configurations against the live SFC specification before saving them. A serverless **SFC Control Plane** (API Gateway + Lambda + DynamoDB + S3) stores versioned configs, assembles self-contained "Launch Packages" complete with AWS IoT X.509 credentials, and streams OpenTelemetry logs from the edge back to CloudWatch. A React/TypeScript single-page app (SPA) served via CloudFront ties all of this together into an operator-facing workflow that goes from an empty text box to a monitored, remotely-controllable edge process in minutes.

---

## Capabilities & Ideas

**The core idea** is that SFC configuration is expert knowledge that most OT engineers lack and most IT teams don't have time to acquire. By grounding an LLM in the actual SFC specification — via an MCP server that reads directly from the SFC GitHub repository — the agent generates correct-by-construction configs rather than plausible-looking but broken JSON. Every generated config is validated by the same MCP tools before it is persisted, creating a tight correctness loop that does not rely on model memorization.

**The control plane** extends this idea to the full device lifecycle. A "Config in Focus" concept — a pinned config version displayed prominently in the UI — makes it unambiguous which configuration will be used the next time a Launch Package is created. Launch Packages are self-contained zip archives that embed the SFC config, an AWS IoT-provisioned X.509 device certificate, a role alias for temporary AWS credential vending, and a runtime agent (`aws-sfc-runtime-agent`). Operators download the zip, unpack it on any Windows, Mac or Linux host, and run a single command. No cloud credentials are baked in; the edge device exchanges its device certificate for short-lived IAM credentials on every session via the AWS IoT Credential Provider.

**Remote operations** are handled over an MQTT5 control channel. From the UI, operators can toggle OpenTelemetry log shipping on or off, switch SFC to TRACE-level diagnostics, push a new config version over-the-air, or trigger a graceful SFC restart — all without touching the edge host. A live heartbeat LED (green / red / grey) reflects device status at a glance, updated every ten seconds.

**AI-assisted remediation** closes the loop. When ERROR-severity OTEL records appear in the log viewer, a single "Fix with AI" click sends the error window and the current SFC config to the agent. The agent diagnoses the errors using its MCP-backed SFC knowledge, returns a corrected config, and the UI renders a side-by-side diff. One more click creates a new Launch Package from the corrected config, preserving the full lineage chain back to the failed deployment.

The result is an end-to-end workflow — from natural-language description to monitored, self-healing edge process — built entirely on AWS serverless primitives with no standing infrastructure costs.

---

## Invoke the Agent (AWS CLI)

The agent runs as an **Amazon Bedrock AgentCore Runtime**. After deployment via `scripts/build_launch_agentcore.py`, retrieve the runtime ARN and invoke it:

```bash
# 1. Get the AgentCore runtime ARN
export AWS_REGION=<YOUR-REGION>
AGENT_RUNTIME_ARN=$(aws bedrock-agentcore-control list-agent-runtimes \
  --region $AWS_REGION \
  --query "agentRuntimes[?agentRuntimeName=='sfc_config_agent'].agentRuntimeArn" \
  --output text)

echo '{"prompt": "Create an OPC-UA SFC config for a press machine with two data sources"}' > input.json

# 2. Invoke the agent
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn "$AGENT_RUNTIME_ARN" \
  --runtime-session-id "sfc-agent-my-session-01-20260225-0001" \
  --payload fileb://input.json \
  --region $AWS_REGION \
  --cli-read-timeout 0 \
  --cli-connect-timeout 0 \
  output.txt && cat output.txt
```

---

## Start the Control Plane UI

The **SFC Control Plane** is a Vite + React SPA served via **Amazon CloudFront**. In local dev, start it against the deployed API:

```bash
# Set the API URL from the CDK output
echo "VITE_API_BASE_URL=<SfcControlPlaneApiUrl>" > ui/.env.local

# Start the dev server
cd ui && npm install && npm run dev
# → http://localhost:5173
```

In production, open the `SfcControlPlaneUiUrl` CloudFront URL from the CDK output directly in a browser.

### Primary operator workflow

```
Browse Config → Edit (Monaco JSON) → Set as Focus → Create Launch Package → Download to Edge → Monitor Logs
```

| UI Route | Purpose |
|---|---|
| `/` | Config File Browser |
| `/configs/:configId` | Monaco JSON Editor — save versions, set focus, create package |
| `/packages` | Launch Package List — live status LED, download, logs, AI-fix |
| `/packages/:packageId` | Package Detail + Runtime Controls |
| `/packages/:packageId/logs` | OTEL Log Viewer — ERROR-highlighted, "Fix with AI" CTA |

---

## Launch Packages

A **Launch Package** is a self-contained zip assembled by the Control Plane — everything needed to run SFC on an edge host:

```
launch-package-{packageId}.zip
├── sfc-config.json          # SFC config with IoT credential provider injected
├── iot/                     # X.509 device cert, private key, Root CA, iot-config.json
├── runner/                  # aws-sfc-runtime-agent (uv / Python 3.12)
└── docker/                  # Optional Dockerfile + build script
```

**Run on the edge host:**

```bash
unzip launch-package-<id>.zip
cd runner && uv run runner.py
```

The `aws-sfc-runtime-agent` handles IoT mTLS credential vending, SFC subprocess management, OTEL log shipping to CloudWatch, and the MQTT control channel back to the cloud.

---

## Runtime Controls & Monitoring

Once a package is `READY`, operators control the live edge device from the Package Detail view:

| Control | Description |
|---|---|
| **Telemetry on/off** | Enable/disable OTEL CloudWatch log shipping |
| **Diagnostics on/off** | Switch SFC log level to TRACE |
| **Push Config Update** | Send a new config version to the edge over MQTT |
| **Restart SFC** | Graceful SFC subprocess restart |

A live **status LED** (green `ACTIVE` / red `ERROR` / grey `INACTIVE`) reflects device heartbeat, polled every 10 s.

---

## AI-Assisted Remediation

When ERROR-severity records appear in the log viewer:

1. Click **"Fix with AI"** and select the error time window
2. The backend invokes the **Bedrock AgentCore SFC Config Agent** with the error logs + current config
3. A side-by-side diff of the corrected config is shown
4. Click **"Create New Launch Package"** — deploys the fixed config as a new package

---

## AI-Guided Config Generation

From the Config Browser, operators can also trigger an AI-guided config creation workflow:

1. Describe the machine, protocol, target AWS service, and data channels in natural language — or upload an existing spec file as context
2. Optionally provide structured fields: protocol, host/port targets, sampling interval
3. The agent calls the MCP server to load relevant SFC adapter and target documentation, generates a config, validates it, and saves it to S3/DynamoDB
4. A job ID is returned immediately (HTTP 202); the UI polls `GET /configs/generate/{jobId}` until status is `COMPLETE`
5. The new config appears in the Config Browser, ready to be set as Focus and packaged

---

## MCP Server — SFC Specification Tools

The agent uses a co-deployed **FastMCP server** (`src/sfc-spec-mcp-server.py`) that reads directly from the [SFC GitHub repository](https://github.com/awslabs/industrial-shopfloor-connect). Available tools:

| Tool | Description |
|---|---|
| `update_repo` | Pull latest SFC spec from GitHub |
| `list_core_docs` / `get_core_doc` | Browse and read core SFC documentation |
| `list_adapter_docs` / `get_adapter_doc` | Browse and read protocol adapter docs |
| `list_target_docs` / `get_target_doc` | Browse and read AWS/edge target docs |
| `query_docs` | Cross-type doc search with optional content inclusion |
| `search_doc_content` | Full-text search across all SFC documentation |
| `extract_json_examples` | Extract parsed JSON config examples from docs |
| `get_sfc_config_examples` | Retrieve component-filtered config examples |
| `create_sfc_config_template` | Generate a typed config template for a protocol/target pair |
| `validate_sfc_config` | Validate a config JSON against SFC schema and knowledge base |
| `what_is_sfc` | Return a structured explanation of SFC capabilities |

Supported protocols: **OPC-UA, Modbus TCP, Siemens S7, MQTT, REST, SQL, SNMP, Allen-Bradley PCCC, Beckhoff ADS, J1939 (CAN Bus), Mitsubishi SLMP, NATS, OPC-DA, Simulator**

Supported AWS targets: **IoT Core, IoT Analytics, IoT SiteWise, S3, S3 Tables (Apache Iceberg), Kinesis, Kinesis Firehose, Lambda, SNS, SQS, Timestream, MSK**

Edge targets: **OPC-UA Server, OPC-UA Writer, Debug, File, MQTT Broker, NATS**

---

## Agent Tools (Internal)

In addition to the MCP tools, the agent has direct access to cloud storage via these built-in tools:

| Tool | Description |
|---|---|
| `read_config_from_file` | Read an SFC config from S3/DynamoDB by filename |
| `save_config_to_file` | Save a config JSON to S3 + DynamoDB; returns a pre-signed download URL |
| `save_results_to_file` | Save arbitrary content (txt, md, csv) to S3 |
| `save_conversation` | Export the last N conversation exchanges as markdown to S3 |
| `read_context_from_file` | Read any previously saved file as agent context |
| `retrieve_session_memory` | Fetch AgentCore Memory records for the current session |

---

## Deployment

```bash
cd agents_catalog/standalone_agents/01-sfc-config-agent/cdk
pip install -r requirements.txt
cdk deploy
```

Key CDK outputs:

| Output | Description |
|---|---|
| `SfcControlPlaneUiUrl` | CloudFront URL for the Control Plane SPA |
| `SfcControlPlaneApiUrl` | API Gateway endpoint |
| `SfcConfigBucketName` | S3 bucket (configs + packages) |
| `SfcLaunchPackageTableName` | DynamoDB Launch Package table |
| `SfcControlPlaneStateTableName` | DynamoDB state table (focus config) |
| `AgentCoreMemoryId` | Short-term memory ID (also in SSM `/sfc-config-agent/memory-id`) |

See the repository-level [deployment guide](../../../docs/deployment.md) for full instructions.

---

## Control Plane API

The API follows the OpenAPI 3.0 spec at `cdk/openapi/control-plane-api.yaml` — this is the single source of truth imported into Amazon API Gateway. All integrations use Lambda proxy (synchronous, Python 3.12).

### Config Management (`/configs`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/configs` | List all configs (latest version per configId) |
| `POST` | `/configs` | Create a new config |
| `GET` | `/configs/focus` | Get the config currently in focus |
| `POST` | `/configs/focus` | Clear focus |
| `GET` | `/configs/{configId}` | Get latest version metadata + S3 content |
| `PUT` | `/configs/{configId}` | Save a new version |
| `DELETE` | `/configs/{configId}` | Soft-delete (marks all versions archived) |
| `PATCH` | `/configs/{configId}/tags` | Update tags |
| `POST` | `/configs/{configId}/focus` | Set a specific version as focus |
| `GET` | `/configs/{configId}/versions` | List all versions |
| `GET` | `/configs/{configId}/versions/{version}` | Get a specific version |
| `POST` | `/configs/generate` | Start AI-guided config generation (async, returns `jobId`) |
| `GET` | `/configs/generate/{jobId}` | Poll generation job status |

### Launch Package Management (`/packages`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/packages` | Full package orchestration: IoT provisioning + zip assembly |
| `GET` | `/packages` | List all packages |
| `GET` | `/packages/{packageId}` | Get package details |
| `DELETE` | `/packages/{packageId}` | Delete package record |
| `PATCH` | `/packages/{packageId}/tags` | Update tags |
| `GET` | `/packages/{packageId}/download` | Get presigned S3 download URL |

### IoT Provisioning (`/packages/{packageId}/iot`)

| Method | Description |
|---|---|
| `POST` | Re-provision: mint fresh X.509 cert for a new package (same config) |
| `GET` | Get provisioning status and IoT resource ARNs |
| `DELETE` | Revoke certificate and delete IoT Thing |

### Logs (`/packages/{packageId}/logs`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/logs` | Paginated OTEL log events (supports `startTime`, `endTime`, `limit`, `lookbackMinutes`) |
| `GET` | `/logs/errors` | ERROR-severity events for a time window (used by AI remediation) |

### Runtime Control (`/packages/{packageId}/control`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/control` | Get persisted control state |
| `PUT` | `/control/telemetry` | Toggle OTEL log shipping on/off |
| `PUT` | `/control/diagnostics` | Toggle TRACE log level on/off |
| `POST` | `/control/config-update` | Push a config version to the edge via MQTT |
| `POST` | `/control/restart` | Trigger graceful SFC subprocess restart |
| `GET` | `/heartbeat` | Get latest heartbeat state (`ACTIVE` / `ERROR` / `INACTIVE`) |

### AI Remediation (`/packages/{packageId}/remediate`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/remediate` | Invoke AI remediation for an error time window; returns corrected config |
| `GET` | `/remediate/{sessionId}` | Poll async remediation session status |

### Greengrass v2 (`/packages/{packageId}/greengrass`)

| Method | Description |
|---|---|
| `POST` | Create a GG v2 component version from a READY launch package |
| `GET` | Get component ARN and deployment status |

---

## Data Model

### `SfcConfigTable` (DynamoDB)

| Attribute | Role |
|---|---|
| `configId` (PK) | Unique config identifier |
| `version` (SK) | ISO timestamp version key |
| `name`, `description` | Human-readable metadata |
| `s3Key` | S3 object key |
| `status` | `active` \| `archived` |
| `createdAt` | Creation timestamp |

### `LaunchPackageTable` (DynamoDB)

| Attribute | Role |
|---|---|
| `packageId` (PK) | UUID |
| `createdAt` (SK) | ISO timestamp |
| `configId`, `configVersion` | Snapshotted config reference |
| `status` | `PROVISIONING` \| `READY` \| `ERROR` |
| `iotThingName`, `iotCertArn`, `iotRoleAliasArn`, `iamRoleArn` | IoT/IAM resources |
| `s3ZipKey`, `logGroupName` | Package storage and logging |
| `telemetryEnabled`, `diagnosticsEnabled` | Persisted control toggles |
| `lastConfigUpdateAt`, `lastConfigUpdateVersion` | Config push tracking |
| `lastRestartAt` | Last restart timestamp |
| `lastHeartbeatAt`, `sfcRunning`, `lastHeartbeatPayload` | Live device status |
| `sourcePackageId` | Lineage: references the failed package that triggered AI remediation |
| `ggComponentArn` | Greengrass v2 component ARN (populated post-creation) |

GSI: `configId-index` for reverse config → package lookup.

### `ControlPlaneStateTable` (DynamoDB)

Singleton table (`stateKey = "global"`) holding the currently focused `configId` + `configVersion`.

### S3 Layout (`SfcConfigBucket`)

| Key Prefix | Contents |
|---|---|
| `configs/{configId}/{version}/config.json` | SFC configuration versions |
| `packages/{packageId}/launch-package.zip` | Assembled edge packages |
| `packages/{packageId}/assets/` | IoT X.509 certs (scoped IAM access only) |
| `ui/` | Vite SPA static build (served exclusively via CloudFront OAC) |

---

## `aws-sfc-runtime-agent` (Edge)

The `runner/runner.py` inside each Launch Package is a self-contained uv-managed Python 3.12 application. It:

1. Reads `iot-config.json` for all runtime parameters (no environment overrides needed)
2. Exchanges the device X.509 certificate for temporary AWS credentials via the IoT Credential Provider (mTLS), refreshed every 50 minutes
3. Downloads SFC binaries from the [SFC GitHub releases](https://github.com/awslabs/industrial-shopfloor-connect/releases) for the version declared in the config
4. Launches SFC as a managed subprocess, capturing stdout/stderr line-by-line
5. Wraps each captured line as an OTEL `LogRecord` and exports to CloudWatch Logs via OTLP/HTTP (`BatchLogRecordProcessor`)
6. Maintains an MQTT5 control channel, subscribing to `sfc/{packageId}/control/+` for telemetry, diagnostics, config-update, and restart commands
7. Publishes a heartbeat every 5 seconds to `sfc/{packageId}/heartbeat` containing `sfcRunning`, `sfcPid`, toggle states, and the last 3 log lines
8. Handles `SIGTERM`/`SIGINT` with graceful OTEL flush, MQTT disconnect, and SFC subprocess termination

**CLI option:** `--no-otel` disables CloudWatch log export (useful for air-gapped environments).

**Docker support:** Each package includes a `Dockerfile` and `docker-build.sh` for containerised deployment on Amazon Corretto 21 + Alpine.

---

## IoT Security Model

Each Launch Package provisions a unique AWS IoT Thing with:

- A fresh X.509 device certificate and private key (stored in `packages/{packageId}/assets/` with IAM-scoped access)
- An IoT policy granting `iot:Connect`, `iot:Subscribe`, `iot:Receive` on the device's own MQTT topics, and `iot:Publish` to its heartbeat topic only
- A role alias enabling temporary credential vending scoped to the minimum IAM permissions derived from the SFC config's target types (IoT Core, SiteWise, Kinesis, S3, CloudWatch Logs)
- A permissions boundary on all dynamically created IAM roles to prevent privilege escalation

Certificate revocation (`DELETE /packages/{packageId}/iot`) is available as a first-class API operation.

---

## Project Structure

```
01-sfc-config-agent/
├── manifest.json                          # Agent registry metadata
├── requirements.txt
├── Dockerfile.deps                        # Dependency image for AgentCore build
├── cdk/
│   ├── stack.py                           # CDK stack entry point
│   ├── control-plane-design.md            # Full architecture design document
│   ├── control-plane-requirements.md
│   ├── openapi/control-plane-api.yaml     # OpenAPI 3.0 spec (API GW source of truth)
│   └── constructs/
│       ├── control_plane_api.py           # API GW + all Lambda functions
│       ├── heartbeat_rule.py              # IoT Topic Rule → DynamoDB heartbeat ingestion
│       ├── launch_package_tables.py       # LaunchPackageTable + ControlPlaneStateTable
│       └── ui_hosting.py                  # CloudFront + S3 OAC construct
├── src/
│   ├── agent.py                           # AgentCore entrypoint (Strands + BedrockAgentCoreApp)
│   ├── sfc-spec-mcp-server.py             # FastMCP server (SFC spec validation tools)
│   ├── sfc-config-example.json            # Reference SFC config
│   ├── lambda_handlers/
│   │   ├── config_handler.py              # fn-configs
│   │   ├── launch_pkg_handler.py          # fn-launch-pkg
│   │   ├── iot_prov_handler.py            # fn-iot-prov
│   │   ├── logs_handler.py                # fn-logs
│   │   ├── gg_comp_handler.py             # fn-gg-comp
│   │   ├── iot_control_handler.py         # fn-iot-control
│   │   ├── agent_create_config_handler.py # fn-agent-create-config
│   │   └── agent_remediate_handler.py     # fn-agent-remediate
│   ├── layer/python/sfc_cp_utils/         # Shared Lambda layer
│   │   ├── ddb.py                         # DynamoDB helpers
│   │   ├── s3.py                          # S3 helpers
│   │   └── iot.py                         # IoT credential endpoint helper
│   ├── tools/
│   │   ├── file_operations.py             # S3/DDB file I/O for agent tools
│   │   ├── sfc_knowledge.py               # SFC knowledge base (protocols, targets)
│   │   ├── sfc_module_analyzer.py
│   │   ├── data_visualizer.py
│   │   └── prompt_logger.py               # Conversation history to S3
│   └── edge/
│       ├── runner.py                      # aws-sfc-runtime-agent
│       └── pyproject.toml
└── ui/                                    # Vite + React + TypeScript SPA
    ├── src/
    │   ├── pages/
    │   │   ├── ConfigBrowser.tsx          # Config list with tag filter + sort
    │   │   ├── ConfigEditor.tsx           # Monaco JSON editor + AI wizard CTA
    │   │   ├── PackageList.tsx            # Package table with live LED column
    │   │   ├── PackageDetail.tsx          # Detail + PackageControlPanel
    │   │   └── LogViewer.tsx              # OTEL log stream + "Fix with AI"
    │   ├── components/
    │   │   ├── AiConfigWizard.tsx         # AI-guided config generation modal
    │   │   ├── MonacoJsonEditor.tsx       # JSON editor with SFC schema
    │   │   ├── HeartbeatStatusLed.tsx     # Live LED (ACTIVE/ERROR/INACTIVE)
    │   │   ├── PackageControlPanel.tsx    # Telemetry/diagnostics/config-push/restart
    │   │   ├── OtelLogStream.tsx          # Colour-coded OTEL log viewer
    │   │   ├── FocusBanner.tsx            # Persistent focused-config banner
    │   │   ├── TagEditor.tsx / TagFilter.tsx
    │   │   ├── StatusBadge.tsx
    │   │   ├── ConfirmDialog.tsx
    │   │   ├── RemediationConfirmDialog.tsx
    │   │   ├── MarkdownRenderer.tsx
    │   │   ├── RefreshButton.tsx
    │   │   └── SortableHeader.tsx
    │   └── api/client.ts                  # Generated API client (from OpenAPI spec)
    └── hooks/useSortable.ts
```
