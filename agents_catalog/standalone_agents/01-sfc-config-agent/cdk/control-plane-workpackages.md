# SFC Config-Agent Control-Plane – Work Packages

## Status Legend
- ✅ Implemented
- ⬜ Not yet implemented

---

## WP-01 · CDK Foundation & DynamoDB Tables ✅

**Goal:** Scaffold control-plane infrastructure under `cdk/`.

### Deliverables

| File | Status |
|---|---|
| `cdk/constructs/launch_package_tables.py` | ✅ |
| `cdk/stack.py` (wires all constructs) | ✅ |

### Tables

| Table | PK | SK | Notes |
|---|---|---|---|
| `SfcLaunchPackageTable` | `packageId` (S) | `createdAt` (S) | Stores launch-package metadata + heartbeat state |
| `SfcControlPlaneStateTable` | `stateKey` (S) | — | Global control-plane key-value state |

---

## WP-02 · OpenAPI 3.0 Specification ✅

**Goal:** Define `cdk/openapi/control-plane-api.yaml` covering all API routes.

### Routes

| Method | Path | Lambda |
|---|---|---|
| `POST/GET/DELETE` | `/configs` / `/configs/{configId}` | fn-configs |
| `POST/GET` | `/launch-packages` / `/launch-packages/{packageId}` | fn-launch-pkg |
| `POST/DELETE/GET` | `/launch-packages/{packageId}/iot-provisioning` | fn-iot-prov |
| `GET` | `/launch-packages/{packageId}/logs` | fn-logs |
| `POST/GET` | `/launch-packages/{packageId}/gg-component` | fn-gg-comp |
| `GET/PUT` | `/launch-packages/{packageId}/control` + sub-routes | fn-iot-control |
| `GET` | `/launch-packages/{packageId}/heartbeat` | fn-iot-control |
| `POST/GET` | `/launch-packages/{packageId}/remediate` + `/{sessionId}` | fn-agent-remediate |

**Deliverable:** `cdk/openapi/control-plane-api.yaml` ✅

---

## WP-03 · Shared Lambda Layer (sfc_cp_utils) ✅

**Goal:** Python layer with DynamoDB, S3, and IoT helper utilities.

### Deliverables

| File | Notes |
|---|---|
| `src/layer/sfc_cp_utils/__init__.py` | ✅ |
| `src/layer/sfc_cp_utils/ddb.py` | `get_package`, `put_package`, `update_package`, `get_config`, `put_config` |
| `src/layer/sfc_cp_utils/s3.py` | `config_s3_key`, `get_config_json`, `put_config_json`, `generate_presigned_url` |
| `src/layer/sfc_cp_utils/iot.py` | `get_iot_data_endpoint` |

---

## WP-04 · Config Management Lambda (fn-configs) ✅

**Goal:** CRUD for SFC config objects in S3 + DynamoDB index.

**Deliverable:** `src/lambda_handlers/config_handler.py` ✅

### Operations
- `POST /configs` — create config, upload JSON to S3, index in DynamoDB
- `GET /configs` — list configs from DynamoDB
- `GET /configs/{configId}` — retrieve config metadata + S3 presigned URL
- `DELETE /configs/{configId}` — soft-delete (update status in DynamoDB)

---

## WP-05 · IoT Provisioning Lambda (fn-iot-prov) ✅

**Goal:** Lifecycle management of IoT thing, certificate, and role alias for a launch package.

**Deliverable:** `src/lambda_handlers/iot_prov_handler.py` ✅

### Operations
- `POST /launch-packages/{packageId}/iot-provisioning` — create thing + cert + role alias → store creds in S3
- `DELETE /launch-packages/{packageId}/iot-provisioning` — revoke cert, detach policies, delete thing
- `GET /launch-packages/{packageId}/iot-provisioning` — return provisioning status

---

## WP-06 · Launch Package Assembly Lambda (fn-launch-pkg) ✅

**Goal:** Assemble and zip edge runtime packages from config + IoT credentials.

**Deliverable:** `src/lambda_handlers/launch_pkg_handler.py` ✅

### Operations
- `POST /launch-packages` — create package record in DynamoDB, trigger assembly
- `GET /launch-packages` — list all packages
- `GET /launch-packages/{packageId}` — get package status + presigned download URL

### Package contents (ZIP)
```
launch-package-{packageId}.zip
├── runner/
│   ├── runner.py
│   ├── pyproject.toml
│   └── uv.lock (generated on first install)
├── sfc-config.json
└── iot/
    ├── iot-config.json
    ├── device.cert.pem
    ├── device.private.key
    └── AmazonRootCA1.pem
```

---

## WP-07 · Log Retrieval Lambda (fn-logs) ✅

**Goal:** Retrieve SFC process logs from CloudWatch for a launch package.

**Deliverable:** `src/lambda_handlers/logs_handler.py` ✅

### Operations
- `GET /launch-packages/{packageId}/logs` — query CloudWatch log group `/sfc/launch-packages/{packageId}`

---

## WP-08 · IoT Runtime Control Lambda + Heartbeat ✅

**Goal:** Runtime control channel over MQTT + heartbeat status endpoint.

### Deliverables

| File | Notes |
|---|---|
| `src/lambda_handlers/iot_control_handler.py` | ✅ — handles REST control endpoints |
| `cdk/constructs/heartbeat_rule.py` | ✅ — IoT Topic Rule → DynamoDB (WP-08b) |

### REST Operations
- `GET /launch-packages/{packageId}/heartbeat` — live status from DynamoDB
- `GET /launch-packages/{packageId}/control` — current telemetry/diagnostics state
- `PUT /launch-packages/{packageId}/control/telemetry` — enable/disable telemetry
- `PUT /launch-packages/{packageId}/control/diagnostics` — enable/disable diagnostics
- `POST /launch-packages/{packageId}/control/config-update` — push new config via presigned URL
- `POST /launch-packages/{packageId}/control/restart` — restart SFC subprocess

### IoT Topic Rule (WP-08b)
- **SQL:** `SELECT *, topic(2) AS packageId FROM 'sfc/+/heartbeat'`
- **Action:** DynamoDB v2 PutItem → `SfcLaunchPackageTable`
- **IAM Role:** `HeartbeatRuleRole` (trust: `iot.amazonaws.com`)

---

## WP-09 · Greengrass Component Lambda (fn-gg-comp) ✅

**Goal:** Create a Greengrass v2 component version from a launch package.

**Deliverable:** `src/lambda_handlers/gg_comp_handler.py` ✅

### Operations
- `POST /launch-packages/{packageId}/gg-component` — create GGv2 component version
  - Validates package is in READY state
  - Checks for recent ERROR logs (last 10 min)
  - Calls `greengrassv2:CreateComponentVersion` with inline recipe
  - Stores `ggComponentArn` in DynamoDB
- `GET /launch-packages/{packageId}/gg-component` — return component ARN + status

---

## WP-10 · AI Remediation Lambda (fn-agent-remediate) ✅

**Goal:** Trigger SFC Config AgentCore to diagnose errors and generate a corrected config.

**Deliverable:** `src/lambda_handlers/agent_remediate_handler.py` ✅

### How it works
1. Fetches ERROR logs from CloudWatch within specified time window
2. Retrieves current SFC config from S3
3. Calls the **SFC Config AgentCore** via `boto3.client("bedrock-agentcore").invoke_agent_runtime()`
   - **Not** Bedrock managed agent runtime
   - AgentCore runtime ID resolved from env var `AGENTCORE_RUNTIME_ID` or SSM `/sfc-config-agent/agentcore-runtime-id`
4. Parses corrected JSON config from agent response
5. Saves corrected config as new version in S3 + DynamoDB

### Operations
- `POST /launch-packages/{packageId}/remediate` — trigger remediation session
- `GET /launch-packages/{packageId}/remediate/{sessionId}` — get session status

### IAM
- `bedrock-agentcore:InvokeAgentRuntime` on `*`
- `ssm:GetParameter` on `/sfc-config-agent/agentcore-runtime-id`

---

## WP-11 · Edge Runtime Agent ✅

**Goal:** Python edge agent that runs on the edge device inside the launch package.

**Deliverables**

| File | Notes |
|---|---|
| `src/edge/runner.py` | ✅ Main edge agent |
| `src/edge/pyproject.toml` | ✅ `uv`-compatible packaging |

### runner.py capabilities
1. **Bootstrap** — downloads SFC jar from GitHub releases; installs Temurin JRE via Adoptium API if Java absent
2. **IoT credential vending** — fetches temp AWS creds from IoT role alias credential endpoint via mTLS
3. **SFC subprocess** — launches `java -jar sfc-{version}-all.jar -config sfc-config.json`, captures stdout/stderr
4. **OTEL log shipping** — ships SFC stdout to CloudWatch via OTLP HTTP endpoint (gateable via `telemetryEnabled`)
5. **MQTT control channel** — subscribes to `sfc/{packageId}/control/#`; handles `telemetry`, `diagnostics`, `config-update`, `restart`
6. **Heartbeat** — publishes `sfc/{packageId}/heartbeat` every 5 s (triggers IoT Rule → DynamoDB WP-08b)
7. **Credential refresh** — re-fetches IoT credentials every 50 min (background thread)
8. **Graceful shutdown** — handles SIGTERM/SIGINT; flushes OTEL; disconnects MQTT; terminates SFC

---

## WP-12 · API Gateway HTTP API CDK Construct ✅

**Goal:** Single CDK construct that provisions all 7 Lambda functions + API GW HTTP API.

**Deliverable:** `cdk/constructs/control_plane_api.py` ✅

### Features
- Shared Lambda layer (`sfc_cp_utils`) attached to all functions
- OpenAPI spec imported via `Fn.sub` ARN injection
- Access logging to CloudWatch with 1-month retention
- Per-function IAM grants (S3, DynamoDB, IoT, CloudWatch Logs, GreengrassV2, AgentCore)
- `fn-agent-remediate` uses `bedrock-agentcore:InvokeAgentRuntime` (corrected from `bedrock-agent-runtime:InvokeAgent`)

---

## WP-18 · CloudFront + S3 UI Hosting CDK Construct ✅

**Goal:** CloudFront distribution serving the SFC Control Plane SPA.

**Deliverable:** `cdk/constructs/ui_hosting.py` ✅

### Architecture
- **S3 origin** (OAC) → serves static SPA from `SfcConfigBucket/ui/*`
- **API Gateway origin** → proxies `/api/*` without cache
- **Custom error responses** → `403/404 → 200 /index.html` for client-side routing
- **HTTPS-only** viewer protocol
- **Origin Access Control** (OAC, replaces legacy OAI)