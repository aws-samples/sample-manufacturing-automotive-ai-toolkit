# SFC Control Plane — Implementation Work Packages

## Overview

This document breaks the [Control Plane Architecture Design](control-plane-design.md) into self-contained, implementable work packages (WPs). Each WP has a defined scope, input dependencies, deliverables, and acceptance criteria.

**Tracks:**
- **I** — Infrastructure (CDK)
- **B** — Backend (Lambda / API)
- **E** — Edge (aws-sfc-runtime-agent)
- **F** — Frontend (Vite + React SPA)
- **V** — Validation (Integration & E2E)

**Recommended sequencing:**

```
WP-01 (I) ──► WP-03 (B) ──► WP-04 … WP-10 (B, parallelisable)
WP-02 (I) ──► WP-12 (I) ──► WP-04 … WP-10
WP-02 (I) ──► WP-13 (F) ──► WP-14 ──► WP-15 ──► WP-16 ──► WP-17
WP-01 (I) ──► WP-18 (I)   [parallel with frontend WPs]
WP-11 (E)                  [independent — no cloud deps during authoring]
WP-19 (V) ──────────────── [all other WPs complete]
```

---

## WP-01 — CDK Foundation & DynamoDB Tables

**Track:** Infrastructure  
**Design refs:** §4.2, §4.3, §11

### Scope

Extend the existing `SfcAgentStack` with the two new DynamoDB tables and establish the CDK construct scaffolding that all subsequent infrastructure WPs will extend.

### Deliverables

| File | Description |
|---|---|
| `cdk/constructs/launch_package_tables.py` | New CDK construct class `LaunchPackageTables` |
| `cdk/sfc_agent_stack.py` | Import and instantiate `LaunchPackageTables`; thread `table` references through to other construct constructors |

#### `LaunchPackageTable` schema

| Attribute | Type | Notes |
|---|---|---|
| `packageId` | S (PK) | UUID |
| `createdAt` | S (SK) | ISO-8601 |
| `configId` | S | GSI partition key |
| `configVersion` | S | — |
| `status` | S | `PROVISIONING` \| `READY` \| `ERROR` |
| `iotThingName` | S | — |
| `iotCertArn` | S | — |
| `iotRoleAliasArn` | S | — |
| `iamRoleArn` | S | — |
| `s3ZipKey` | S | — |
| `logGroupName` | S | — |
| `ggComponentArn` | S | Optional |
| `sourcePackageId` | S | Optional — lineage from re-provisioning |
| `telemetryEnabled` | BOOL | Default `true` |
| `diagnosticsEnabled` | BOOL | Default `false` |
| `lastConfigUpdateAt` | S | — |
| `lastConfigUpdateVersion` | S | — |
| `lastRestartAt` | S | — |
| `lastHeartbeatAt` | S | Written by IoT Rule |
| `lastHeartbeatPayload` | S | Full JSON string (max ~1 KB) |
| `sfcRunning` | BOOL | From last heartbeat |

- `PAY_PER_REQUEST` billing
- Point-in-time recovery (PITR) enabled
- GSI: `configId-index` (PK: `configId`)

#### `ControlPlaneStateTable` schema

| Attribute | Type | Notes |
|---|---|---|
| `stateKey` | S (PK) | Always `"global"` |
| `focusedConfigId` | S | — |
| `focusedConfigVersion` | S | — |
| `updatedAt` | S | — |

- `PAY_PER_REQUEST`, PITR enabled

### Acceptance Criteria

- [ ] `cdk synth` succeeds with both tables in the synthesised CloudFormation template
- [ ] GSI `configId-index` present on `LaunchPackageTable`
- [ ] PITR enabled on both tables
- [ ] Table ARNs exported as CDK `CfnOutput` values for cross-construct reference
- [ ] No regression in existing `SfcConfigTable` or `SfcConfigBucket` resources

---

## WP-02 — OpenAPI 3.0 Specification

**Track:** Infrastructure  
**Design refs:** §3, §3.1–§3.7

### Scope

Author the complete OpenAPI 3.0 specification for the Control Plane HTTP API. This is the **single source of truth** for both the API Gateway import (WP-12) and the auto-generated TypeScript HTTP client (WP-13).

### Deliverables

| File | Description |
|---|---|
| `cdk/openapi/control-plane-api.yaml` | Full OpenAPI 3.0 spec |

### Endpoint Inventory

All endpoints below must be fully specified with request bodies, path/query parameters, response schemas (200, 400, 404, 409, 500), and `x-amazon-apigateway-integration` extensions for Lambda proxy.

#### Config Management

| Method | Path |
|---|---|
| `GET` | `/configs` |
| `GET` | `/configs/focus` |
| `POST` | `/configs/{configId}/focus` |
| `GET` | `/configs/{configId}` |
| `GET` | `/configs/{configId}/versions` |
| `GET` | `/configs/{configId}/versions/{version}` |
| `PUT` | `/configs/{configId}` |

#### Launch Package Management

| Method | Path |
|---|---|
| `POST` | `/packages` |
| `GET` | `/packages` |
| `GET` | `/packages/{packageId}` |
| `GET` | `/packages/{packageId}/download` |
| `DELETE` | `/packages/{packageId}` |

#### IoT Provisioning

| Method | Path |
|---|---|
| `POST` | `/packages/{packageId}/iot` |
| `GET` | `/packages/{packageId}/iot` |
| `DELETE` | `/packages/{packageId}/iot` |

#### Log Retrieval

| Method | Path |
|---|---|
| `GET` | `/packages/{packageId}/logs` |
| `GET` | `/packages/{packageId}/logs/errors` |

#### Greengrass Component

| Method | Path |
|---|---|
| `POST` | `/packages/{packageId}/greengrass` |
| `GET` | `/packages/{packageId}/greengrass` |

#### Runtime Control

| Method | Path |
|---|---|
| `GET` | `/packages/{packageId}/control` |
| `PUT` | `/packages/{packageId}/control/telemetry` |
| `PUT` | `/packages/{packageId}/control/diagnostics` |
| `POST` | `/packages/{packageId}/control/config-update` |
| `POST` | `/packages/{packageId}/control/restart` |
| `GET` | `/packages/{packageId}/heartbeat` |

#### AI Remediation

| Method | Path |
|---|---|
| `POST` | `/packages/{packageId}/remediate` |
| `GET` | `/packages/{packageId}/remediate/{sessionId}` |

### Acceptance Criteria

- [ ] Spec validates cleanly with `openapi-generator validate` or `spectral lint`
- [ ] All 28 endpoints have complete request/response schemas
- [ ] All response schemas include error cases (400, 404, 409, 500)
- [ ] `x-amazon-apigateway-integration` extensions present on every operation with correct Lambda ARN placeholders (`!Sub` compatible)
- [ ] CORS headers defined at spec level for `localhost:5173` and the CloudFront origin placeholder
- [ ] TypeScript client can be generated from the spec without errors (`openapi-typescript-codegen`)

---

## WP-03 — Shared Lambda Layer (`sfc_cp_utils`)

**Track:** Backend  
**Design refs:** §3 (shared utilities), §11 (CDK layer construct)  
**Depends on:** WP-01

### Scope

Implement and package the shared Python utility layer used by all Lambda functions. Abstracts DynamoDB, S3, and IoT operations to avoid code duplication across handlers.

### Deliverables

| File | Description |
|---|---|
| `src/layer/sfc_cp_utils/__init__.py` | Package init |
| `src/layer/sfc_cp_utils/ddb.py` | DynamoDB helpers |
| `src/layer/sfc_cp_utils/s3.py` | S3 helpers |
| `src/layer/sfc_cp_utils/iot.py` | IoT provisioning + credential endpoint helper |
| `cdk/constructs/control_plane_api.py` | Initial skeleton — `SfcCpLambdaLayer` CDK construct only (Lambda functions added in subsequent WPs) |

#### `ddb.py` — key functions

```python
def get_config(table, config_id: str, version: str = None) -> dict
def list_configs(table) -> list[dict]
def put_config(table, item: dict) -> None
def get_package(table, package_id: str) -> dict
def put_package(table, item: dict) -> None
def update_package(table, package_id: str, attrs: dict) -> None
def get_control_state(state_table, state_key: str = "global") -> dict
def put_control_state(state_table, item: dict) -> None
```

#### `s3.py` — key functions

```python
def get_config_json(bucket: str, s3_key: str) -> dict
def put_config_json(bucket: str, s3_key: str, config: dict) -> None
def put_zip(bucket: str, s3_key: str, zip_bytes: bytes) -> None
def generate_presigned_url(bucket: str, s3_key: str, ttl_seconds: int = 300) -> str
def put_cert_asset(bucket: str, package_id: str, filename: str, content: str) -> str
```

#### `iot.py` — key functions

```python
def provision_thing(package_id: str, region: str) -> dict
    # Returns: { thingName, certArn, certPem, privateKey, roleAliasArn, iamRoleArn, iotEndpoint }

def derive_iam_policy_statements(sfc_config: dict) -> list[dict]
    # Inspects targets section; returns minimal IAM policy statements

def get_iot_credential_endpoint(region: str) -> str

def revoke_and_delete_thing(thing_name: str, cert_arn: str, role_alias_arn: str, iam_role_arn: str) -> None
```

### Acceptance Criteria

- [ ] Layer zips and deploys via `cdk deploy` without import errors
- [ ] Unit tests pass for all `ddb.py`, `s3.py`, `iot.py` functions (mocked boto3)
- [ ] `SfcCpLambdaLayer` CDK construct produces a valid Lambda layer version
- [ ] All Lambda functions referencing the layer can `import sfc_cp_utils` successfully in a local test

---

## WP-04 — Config Management Lambda (`fn-configs`)

**Track:** Backend  
**Design refs:** §3.1  
**Depends on:** WP-01, WP-02, WP-03

### Scope

Implement the `fn-configs` Lambda handler covering all 7 config management endpoints. All persistence operations must use `sfc_cp_utils` layer helpers.

### Deliverables

| File | Description |
|---|---|
| `src/lambda_handlers/config_handler.py` | Handler (extended from existing baseline if present) |
| `cdk/constructs/control_plane_api.py` | Add `fn-configs` Lambda + IAM role to construct |

### Endpoint Behaviour

| Endpoint | Behaviour |
|---|---|
| `GET /configs` | DDB scan `SfcConfigTable`; return latest version per `configId` using projection |
| `GET /configs/focus` | DDB `GetItem` on `ControlPlaneStateTable` with `stateKey="global"` |
| `POST /configs/{configId}/focus` | DDB `UpdateItem` on `ControlPlaneStateTable`; validates `configId` + `version` exist in `SfcConfigTable` first |
| `GET /configs/{configId}` | DDB `GetItem` latest version + S3 `GetObject` for config content |
| `GET /configs/{configId}/versions` | DDB `Query` on `configId` (all SK values) |
| `GET /configs/{configId}/versions/{version}` | DDB `GetItem` + S3 `GetObject` |
| `PUT /configs/{configId}` | Validate JSON body; DDB `PutItem` new version (SK = `now().isoformat()`); S3 `PutObject` at `configs/{configId}/{version}/config.json` |

### IAM Permissions

- `s3:GetObject`, `s3:PutObject` on `SfcConfigBucket/configs/*`
- `dynamodb:Query`, `dynamodb:PutItem`, `dynamodb:Scan`, `dynamodb:GetItem`, `dynamodb:UpdateItem` on `SfcConfigTable` + `ControlPlaneStateTable`

### Acceptance Criteria

- [ ] All 7 endpoints return correct HTTP status codes and response bodies per the OpenAPI spec
- [ ] `PUT /configs/{configId}` increments version correctly and object is readable from S3
- [ ] `POST /configs/{configId}/focus` rejects unknown `configId`/`version` with `404`
- [ ] Handler integrated into CDK construct and wired to API Gateway via OpenAPI spec

---

## WP-05 — IoT Provisioning Lambda (`fn-iot-prov`)

**Track:** Backend  
**Design refs:** §3.3  
**Depends on:** WP-01, WP-02, WP-03

### Scope

Implement the `fn-iot-prov` Lambda for IoT Thing/certificate/role lifecycle management. **Initial provisioning logic is in `sfc_cp_utils/iot.py`** (WP-03) and called directly by `fn-launch-pkg` (WP-06) — this Lambda covers independent lifecycle operations only (re-provisioning, status inspection, cert revocation).

### Deliverables

| File | Description |
|---|---|
| `src/lambda_handlers/iot_prov_handler.py` | Handler |
| `cdk/constructs/control_plane_api.py` | Add `fn-iot-prov` Lambda + IAM role |

### Endpoint Behaviour

| Endpoint | Behaviour |
|---|---|
| `POST /packages/{packageId}/iot` | Re-provisioning: mint new IoT cert; create new `packageId` inheriting `configId` and `configVersion` from source package; set `sourcePackageId`; preserve original package unchanged |
| `GET /packages/{packageId}/iot` | Return `iotThingName`, `iotCertArn`, `iotRoleAliasArn`, `iamRoleArn` from `LaunchPackageTable` |
| `DELETE /packages/{packageId}/iot` | Call `sfc_cp_utils.iot.revoke_and_delete_thing`; update package `status=ERROR` |

### IAM Policy Derivation Logic

Inside `sfc_cp_utils/iot.py`, `derive_iam_policy_statements` inspects `targets` section:

| SFC Target Type | IAM Actions Added |
|---|---|
| `AwsIotTarget` | `iot:Publish` on topic ARN |
| `AwsSiteWiseTarget` | `iotsitewise:BatchPutAssetPropertyValue` |
| `KinesisTarget` | `kinesis:PutRecord`, `kinesis:PutRecords` |
| `S3Target` | `s3:PutObject` |
| CloudWatch OTEL | `logs:CreateLogGroup`, `logs:CreateLogDelivery`, `logs:PutLogEvents`, `logs:DescribeLogStreams` on `/sfc/launch-packages/{packageId}` |

A **permissions boundary** managed policy is attached to every dynamically created IAM role.

### IoT Policy (per Thing)

```
iot:Connect     → client/sfc-{packageId}
iot:Subscribe   → topicfilter/sfc/{packageId}/control/*
iot:Receive     → topic/sfc/{packageId}/control/*
iot:Publish     → topic/sfc/{packageId}/heartbeat
```

### IAM Permissions for `fn-iot-prov`

- `iot:CreateThing`, `iot:CreateKeysAndCertificate`, `iot:AttachPolicy`, `iot:CreateRoleAlias`
- `iam:CreateRole`, `iam:PutRolePolicy`, `iam:AttachRolePolicy` (with `PermissionsBoundary` condition)
- `logs:CreateLogGroup` on `/sfc/launch-packages/*`
- `s3:PutObject` on `SfcConfigBucket/packages/*/assets/`
- `dynamodb:GetItem`, `dynamodb:UpdateItem` on `LaunchPackageTable`

### Acceptance Criteria

- [ ] Re-provisioning creates a new `packageId` with `sourcePackageId` set; original package record unchanged
- [ ] `DELETE` revokes certificate (IoT cert status = `INACTIVE`) and deletes Thing in AWS IoT
- [ ] Permissions boundary policy caps effective permissions; no `iam:*` actions possible on dynamically created roles
- [ ] IoT policy grants exactly the 4 control-channel actions listed above
- [ ] Lambda memory: 128 MB, timeout: 30 s

---

## WP-06 — Launch Package Assembly Lambda (`fn-launch-pkg`)

**Track:** Backend  
**Design refs:** §3.2, §6  
**Depends on:** WP-01, WP-02, WP-03, WP-05 (IoT provisioning via shared layer)

### Scope

Implement the `fn-launch-pkg` Lambda — the most complex backend function. Orchestrates the full package creation pipeline: config snapshot → IoT provisioning → SFC config rewrite → in-memory zip assembly → S3 upload → status update.

### Deliverables

| File | Description |
|---|---|
| `src/lambda_handlers/launch_pkg_handler.py` | Handler |
| `cdk/constructs/control_plane_api.py` | Add `fn-launch-pkg` Lambda (512 MB, 60 s timeout) + IAM role |

### `POST /packages` Orchestration Steps

1. Create `LaunchPackageTable` record: `status=PROVISIONING`
2. Read focused SFC config from `SfcConfigBucket` (`sfc_cp_utils.s3.get_config_json`)
3. Call `sfc_cp_utils.iot.provision_thing(package_id, region)` — returns `{thingName, certArn, certPem, privateKey, roleAliasArn, iamRoleArn, iotEndpoint}`
4. Rewrite SFC config: inject `AwsIotCredentialProviderClients` block + update all AWS target `AwsCredentialClient` references
5. Build `iot-config.json`:
   ```json
   {
     "iotEndpoint": "...",
     "thingName": "sfc-{packageId}",
     "roleAlias": "sfc-role-alias-{packageId}",
     "region": "{region}",
     "logGroupName": "/sfc/launch-packages/{packageId}",
     "packageId": "{packageId}",
     "configId": "{configId}",
     "topicPrefix": "sfc/{packageId}/control"
   }
   ```
6. Assemble zip **in-memory** (`io.BytesIO` + `zipfile.ZipFile`) with structure from design §6
7. Upload zip to `SfcConfigBucket/packages/{packageId}/launch-package.zip`
8. Upload certs to `packages/{packageId}/assets/`
9. Update `LaunchPackageTable`: `status=READY`, populate all IoT/IAM ARN fields
10. Return `{ packageId, status: "READY", downloadUrl }` (presigned URL, 1 h TTL)

### Zip Contents

```
launch-package-{packageId}.zip
├── sfc-config.json              ← rewritten with IoT credential provider
├── iot/
│   ├── device.cert.pem
│   ├── device.private.key
│   ├── AmazonRootCA1.pem
│   └── iot-config.json
├── runner/
│   ├── pyproject.toml
│   ├── .python-version
│   └── runner.py               ← bundled from src/edge/runner.py
├── docker/
│   ├── Dockerfile
│   └── docker-build.sh
└── README.md
```

### `GET /packages/{packageId}/download`

Returns a fresh presigned S3 URL (1 h TTL) for the zip.

### IAM Permissions for `fn-launch-pkg`

- `s3:GetObject` on `SfcConfigBucket/configs/*`
- `s3:PutObject`, `s3:GetObject` on `SfcConfigBucket/packages/*`
- `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:GetItem` on `LaunchPackageTable`
- `dynamodb:GetItem` on `SfcConfigTable`
- All IoT + IAM permissions delegated via `sfc_cp_utils.iot` (same permissions as `fn-iot-prov`)

### Acceptance Criteria

- [ ] Zip file is valid, extractable, and contains all required paths listed above
- [ ] `sfc-config.json` inside the zip contains `AwsIotCredentialProviderClients` block with correct `ThingName` and `RoleAlias`
- [ ] `iot-config.json` contains all 8 required fields
- [ ] `LaunchPackageTable` record transitions `PROVISIONING → READY`
- [ ] Lambda memory: 512 MB, timeout: 60 s
- [ ] Private key is NOT returned in the API response body; stored only in S3 `packages/*/assets/`

---

## WP-07 — Log Retrieval Lambda (`fn-logs`)

**Track:** Backend  
**Design refs:** §3.4  
**Depends on:** WP-01, WP-02, WP-03

### Scope

Implement `fn-logs` Lambda for paginated CloudWatch log retrieval and error-window filtering.

### Deliverables

| File | Description |
|---|---|
| `src/lambda_handlers/logs_handler.py` | Handler |
| `cdk/constructs/control_plane_api.py` | Add `fn-logs` Lambda + IAM role |

### Endpoint Behaviour

| Endpoint | Query Params | Behaviour |
|---|---|---|
| `GET /packages/{packageId}/logs` | `startTime`, `endTime`, `nextToken`, `limit` (default 200) | `logs:FilterLogEvents` on `/sfc/launch-packages/{packageId}`; returns paginated OTEL records with `nextToken` |
| `GET /packages/{packageId}/logs/errors` | `startTime`, `endTime` | Same but filter pattern `SeverityText=ERROR OR SeverityNumber >= 17`; used as input to AI remediation |

### IAM Permissions

- `logs:FilterLogEvents`, `logs:GetLogEvents`, `logs:DescribeLogGroups` on `/sfc/launch-packages/*`
- `dynamodb:GetItem` on `LaunchPackageTable` (to resolve `logGroupName`)

### Acceptance Criteria

- [ ] Pagination (`nextToken`) works correctly across multi-page result sets
- [ ] Error-window filter returns only `SeverityText=ERROR` and `SeverityNumber >= 17` records
- [ ] Returns `404` when `packageId` does not exist in `LaunchPackageTable`
- [ ] Returns `404` when log group has not yet been created (package in `PROVISIONING`)

---

## WP-08 — IoT Runtime Control Lambda & Heartbeat Rule (`fn-iot-control`)

**Track:** Backend  
**Design refs:** §3.6, §11 (`heartbeat_rule.py` construct)  
**Depends on:** WP-01, WP-02, WP-03

### Scope

Implement `fn-iot-control` Lambda (6 endpoints) and the `SfcHeartbeatRule` IoT Topic Rule CDK construct. This WP enables the live device control panel and heartbeat LED.

### Deliverables

| File | Description |
|---|---|
| `src/lambda_handlers/iot_control_handler.py` | Handler |
| `cdk/constructs/control_plane_api.py` | Add `fn-iot-control` Lambda (128 MB, 15 s timeout) + IAM role |
| `cdk/constructs/heartbeat_rule.py` | New `SfcHeartbeatRule` CDK construct |

### Endpoint Behaviour

| Endpoint | Body | Behaviour |
|---|---|---|
| `GET /packages/{packageId}/control` | — | Returns `telemetryEnabled`, `diagnosticsEnabled`, `lastConfigUpdateAt`, `lastConfigUpdateVersion`, `lastRestartAt` from `LaunchPackageTable`; returns `"unknown"` for missing attributes (pre-feature packages) |
| `PUT .../control/telemetry` | `{"enabled": bool}` | Publishes `{"enabled": bool}` to `sfc/{packageId}/control/telemetry` (QoS 1); updates `telemetryEnabled` in `LaunchPackageTable` |
| `PUT .../control/diagnostics` | `{"enabled": bool}` | Publishes to `sfc/{packageId}/control/diagnostics` (QoS 1); updates `diagnosticsEnabled` |
| `POST .../control/config-update` | `{"configId": str, "configVersion": str}` | Generates S3 presigned URL (5 min TTL); publishes `{"presignedUrl": "..."}` to `sfc/{packageId}/control/config-update`; updates `lastConfigUpdateAt` + `lastConfigUpdateVersion` |
| `POST .../control/restart` | — | Publishes `{"restart": true}` to `sfc/{packageId}/control/restart`; updates `lastRestartAt` |
| `GET /packages/{packageId}/heartbeat` | — | Returns `lastHeartbeatAt`, `sfcRunning`, `recentLogs` from `LaunchPackageTable`; calculates `liveStatus`: `ACTIVE` (heartbeat < 15 s + `sfcRunning=true`), `ERROR` (heartbeat < 15 s + `sfcRunning=false`), `INACTIVE` (heartbeat > 15 s or absent) |

All publish endpoints return `409 Conflict` when `LaunchPackageTable.status != READY`.

### `SfcHeartbeatRule` CDK Construct

```python
# IoT SQL
"SELECT *, topic(2) AS packageId FROM 'sfc/+/heartbeat'"

# DynamoDB action — PutItem on LaunchPackageTable
{
  "packageId":           "${packageId}",
  "lastHeartbeatAt":    "${timestamp()}",
  "lastHeartbeatPayload": "${aws:raw-message}",
  "sfcRunning":         "${sfcRunning}"
}
```

- Dedicated IAM role: `dynamodb:PutItem` on `LaunchPackageTable`

### IAM Permissions for `fn-iot-control`

- `iot:Publish` on `arn:aws:iot:{region}:{account}:topic/sfc/*/control/*`
- `s3:GetObject` on `SfcConfigBucket/configs/*` (for presigned URL generation)
- `dynamodb:GetItem`, `dynamodb:UpdateItem` on `LaunchPackageTable`

### Acceptance Criteria

- [ ] `PUT .../control/telemetry` publishes MQTT message and persists state; UI can immediately read new state from `GET .../control`
- [ ] `GET .../control` returns `"unknown"` for packages created before this feature
- [ ] `GET .../heartbeat` correctly returns `ACTIVE`/`ERROR`/`INACTIVE` based on 15-second threshold
- [ ] IoT Rule writes `lastHeartbeatAt`, `sfcRunning`, `lastHeartbeatPayload` to `LaunchPackageTable` correctly
- [ ] All publish calls return `409` when package `status != READY`
- [ ] Lambda memory: 128 MB, timeout: 15 s

---

## WP-09 — Greengrass Component Lambda (`fn-gg-comp`)

**Track:** Backend  
**Design refs:** §3.5, §10  
**Depends on:** WP-01, WP-02, WP-03, WP-06

### Scope

Implement `fn-gg-comp` Lambda for AWS IoT Greengrass v2 component creation from a READY launch package.

### Deliverables

| File | Description |
|---|---|
| `src/lambda_handlers/gg_comp_handler.py` | Handler |
| `cdk/constructs/control_plane_api.py` | Add `fn-gg-comp` Lambda + IAM role |

### Endpoint Behaviour

| Endpoint | Behaviour |
|---|---|
| `POST /packages/{packageId}/greengrass` | Assemble GGv2 component recipe (see below); call `greengrassv2:CreateComponentVersion`; write `ggComponentArn` to `LaunchPackageTable` |
| `GET /packages/{packageId}/greengrass` | Return `ggComponentArn` and component deployment status |

### GGv2 Recipe Template

```json
{
  "RecipeFormatVersion": "2020-01-25",
  "ComponentName": "com.sfc.{configName}",
  "ComponentVersion": "{YYYY.MM.DD.HHmmss}",
  "ComponentDescription": "SFC runner for config {configName}",
  "ComponentPublisher": "SFC Control Plane",
  "Manifests": [{
    "Platform": { "os": "linux" },
    "Artifacts": [{
      "URI": "s3://{SfcConfigBucket}/packages/{packageId}/launch-package.zip",
      "Unarchive": "ZIP",
      "Permission": { "Read": "OWNER" }
    }],
    "Lifecycle": {
      "Install": "pip install uv && cd {artifacts:path}/runner && uv sync --frozen",
      "Run": "cd {artifacts:path}/runner && uv run runner.py"
    }
  }]
}
```

Precondition: `LaunchPackageTable.status = READY` and no ERROR-severity log records in the past 10 minutes (checked via `fn-logs` helpers from layer).

### IAM Permissions

- `greengrassv2:CreateComponentVersion`
- `s3:GetObject` on `SfcConfigBucket/packages/*`
- `dynamodb:GetItem`, `dynamodb:UpdateItem` on `LaunchPackageTable`

### Acceptance Criteria

- [ ] Returns `409` if package is not `READY`
- [ ] Returns `409` if ERROR-severity logs exist within the last 10 minutes
- [ ] `ggComponentArn` written to `LaunchPackageTable` after successful creation
- [ ] Component version format is `YYYY.MM.DD.HHmmss` (compatible with GGv2 semver-like versioning)
- [ ] `GET` endpoint returns `ggComponentArn` and component deployment status

---

## WP-10 — AI Remediation Lambda (`fn-agent-remediate`)

**Track:** Backend  
**Design refs:** §3.7, §9  
**Depends on:** WP-01, WP-02, WP-03, WP-07

### Scope

Implement `fn-agent-remediate` Lambda — bridges the UI to the Bedrock SFC AgentCore. All agent invocation and response handling is server-side; the corrected config is persisted atomically before returning to the browser.

### Deliverables

| File | Description |
|---|---|
| `src/lambda_handlers/agent_remediate_handler.py` | Handler |
| `cdk/constructs/control_plane_api.py` | Add `fn-agent-remediate` Lambda (256 MB, 120 s timeout) + IAM role |

### Endpoint Behaviour

| Endpoint | Behaviour |
|---|---|
| `POST /packages/{packageId}/remediate` | Full server-side orchestration (see flow below); returns `{ sessionId, newConfigVersion, correctedConfig }` |
| `GET /packages/{packageId}/remediate/{sessionId}` | Poll session status for async fallback; returns `{ status, newConfigVersion, correctedConfig }` once complete |

### `POST /packages/{packageId}/remediate` — Request Body

```json
{
  "errorWindowStart": "<ISO8601>",
  "errorWindowEnd":   "<ISO8601>"
}
```

### Internal Orchestration Flow

1. Fetch error log records via `sfc_cp_utils` log helpers (`GET .../logs/errors` logic reused)
2. Fetch current SFC config JSON from `SfcConfigBucket` (`sfc_cp_utils.s3.get_config_json`)
3. Construct AgentCore prompt:
   > *"The following SFC process errors were observed during Launch Package `{packageId}` execution. The SFC config used is attached. Please diagnose and return a corrected SFC config JSON."*
4. Invoke Bedrock AgentCore (`bedrock-agent-runtime:InvokeAgent`) — collect streamed response
5. Extract corrected config JSON from streamed response text
6. Persist corrected config as new version: `sfc_cp_utils.s3.put_config_json` + `sfc_cp_utils.ddb.put_config`
7. Return `{ sessionId, newConfigVersion, correctedConfig }` to UI

### IAM Permissions

- `s3:GetObject` on `SfcConfigBucket/configs/*`
- `s3:PutObject` on `SfcConfigBucket/configs/*` (new corrected version)
- `dynamodb:PutItem` on `SfcConfigTable`
- `dynamodb:GetItem` on `LaunchPackageTable`
- `bedrock-agent-runtime:InvokeAgent` on the SFC AgentCore ARN
- `logs:FilterLogEvents` on `/sfc/launch-packages/*`

### Acceptance Criteria

- [ ] Lambda timeout: 120 s; memory: 256 MB
- [ ] Corrected config persisted as a new version in `SfcConfigTable` + `SfcConfigBucket` before response is returned
- [ ] `sessionId` is stable across `POST` and `GET` endpoints (same Bedrock session)
- [ ] Returns `504` (via API GW) or structured error body if AgentCore times out or returns no parseable JSON
- [ ] `GET .../remediate/{sessionId}` returns `{ status: "PENDING" }` while in-flight and `{ status: "COMPLETE", ... }` once done

---

## WP-11 — Edge Runtime Agent (`aws-sfc-runtime-agent`)

**Track:** Edge  
**Design refs:** §7, §8  
**Depends on:** None (self-contained; can be authored in parallel with all other WPs)

### Scope

Implement the complete `runner/runner.py` edge agent and its packaging artifacts. The agent is bundled into the launch package zip by `fn-launch-pkg` (WP-06); all runtime parameters are read from `iot-config.json` burnt in at package creation time.

### Deliverables

| File | Description |
|---|---|
| `src/edge/runner.py` | Main edge agent |
| `src/edge/pyproject.toml` | uv project definition |
| `src/edge/.python-version` | Python version pin (`3.12`) |
| `src/edge/docker/Dockerfile` | Container image definition |
| `src/edge/docker/docker-build.sh` | Build + tag helper script |

### `pyproject.toml` Dependencies

```toml
[project]
name = "aws-sfc-runtime-agent"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = [
    "opentelemetry-api",
    "opentelemetry-sdk",
    "aws-opentelemetry-distro",
    "opentelemetry-exporter-otlp-proto-http",
    "awsiotsdk",
    "boto3",
    "requests",
]
```

### Runner Responsibilities (in startup order)

1. **Bootstrap** — read `iot-config.json`; resolve SFC version from `sfc-config.json` `$sfc-version` field; download SFC binaries from GitHub releases; detect/install Java via Adoptium API if absent

2. **IoT credential vending** — mTLS GET to `https://credentials.iot.{region}.amazonaws.com/role-aliases/{roleAlias}/credentials`; inject `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` into subprocess environment

3. **SFC subprocess** — `subprocess.Popen` in daemon thread with `stdout=PIPE, stderr=PIPE`; line-by-line capture into thread-safe ring buffer (last 3 lines)

4. **OTEL log shipping** — `BatchLogRecordProcessor` → `OTLPLogExporter` → CloudWatch OTLP endpoint; severity parsed from line content (`ERROR`/`WARN`/`WARNING`/`DEBUG` keywords); skipped entirely when `--no-otel` flag is set

5. **MQTT5 control channel** — connect with device cert/key/CA from `iot-config.json`; subscribe to `{topicPrefix}/+`; dispatch on `on_message_received` callback to worker thread:

   | Topic suffix | Payload | Action |
   |---|---|---|
   | `/telemetry` | `{"enabled": bool}` | Attach/detach OTEL `BatchLogRecordProcessor` |
   | `/diagnostics` | `{"enabled": bool}` | Set SFC log level `TRACE`/`INFO` |
   | `/config-update` | `{"presignedUrl": "..."}` | Download new `sfc-config.json`; overwrite local file; restart SFC subprocess |
   | `/restart` | `{"restart": true}` | Graceful SFC subprocess restart |

6. **Heartbeat publisher** — background thread, every 5 s, QoS 0, topic `sfc/{packageId}/heartbeat`:
   ```json
   {
     "packageId": "...", "timestamp": "...", "sfcPid": 12345,
     "sfcRunning": true, "telemetryEnabled": true, "diagnosticsEnabled": false,
     "recentLogs": ["[...] INFO ...", "[...] INFO ...", "[...] WARN ..."]
   }
   ```

7. **Credential refresh** — background thread re-fetches IoT credentials every 50 minutes

8. **Graceful shutdown** — `SIGTERM`/`SIGINT` handler: flush OTEL `LoggerProvider`, stop MQTT client, terminate SFC subprocess

### Dockerfile

```dockerfile
FROM amazoncorretto:21-alpine AS base
RUN apk add --no-cache python3 py3-pip curl
RUN curl -Ls https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"
WORKDIR /sfc
COPY sfc-config.json ./
COPY iot/ ./iot/
COPY runner/ ./runner/
WORKDIR /sfc/runner
RUN uv sync --frozen
ENTRYPOINT ["uv", "run", "runner.py"]
```

`docker-build.sh` builds and tags as `aws-sfc-runtime-agent:{packageId}` and prints run instructions.

### CLI Options

| Option | Effect |
|---|---|
| `--no-otel` | Disable OTEL CloudWatch delivery; SFC output written to `sys.stdout` as-is |

### Acceptance Criteria

- [ ] Agent starts and connects to IoT endpoint using packaged mTLS certs
- [ ] SFC subprocess launches and its stdout/stderr are captured line-by-line
- [ ] OTEL log records appear in CloudWatch log group `/sfc/launch-packages/{packageId}` with correct `SeverityText`
- [ ] Heartbeat published every 5 s; `sfcRunning=false` sent immediately on subprocess exit
- [ ] All 4 control topics trigger the correct behaviour (verified by injecting test MQTT messages)
- [ ] `--no-otel` flag completely suppresses CloudWatch export; no errors logged
- [ ] Credential refresh thread re-fetches and re-injects credentials without restarting the SFC subprocess
- [ ] `SIGTERM` causes clean shutdown: OTEL flush confirmed, MQTT disconnect, SFC subprocess terminated

---

## WP-12 — API Gateway HTTP API CDK Construct

**Track:** Infrastructure  
**Design refs:** §3, §11 (`control_plane_api.py`)  
**Depends on:** WP-02, WP-03, WP-04, WP-05, WP-06, WP-07, WP-08, WP-09, WP-10

### Scope

Wire all Lambda functions into the API Gateway HTTP API using the OpenAPI 3.0 spec as the import source. Configure CORS, stage, and CloudWatch access logging.

### Deliverables

| File | Description |
|---|---|
| `cdk/constructs/control_plane_api.py` | Complete `ControlPlaneApi` CDK construct (all Lambdas + HTTP API) |

### Key CDK Configuration

- `HttpApi` with `ApiDefinition.from_asset("openapi/control-plane-api.yaml")` (OpenAPI import mode)
- All Lambda ARNs injected into the spec via CDK `Fn.sub` token substitution before import
- `CorsPreflightOptions`: `allowed_origins=["http://localhost:5173", f"https://{cloudfront_domain}"]`, all methods, all headers
- Default stage with auto-deploy enabled
- CloudWatch access logging to a dedicated log group
- `$default` route throttling: 100 RPS burst, 50 RPS steady

### CDK Outputs (from this construct)

| Output | Value |
|---|---|
| `SfcControlPlaneApiUrl` | `HttpApi.url` |

### Acceptance Criteria

- [ ] `cdk synth` produces valid CloudFormation with API Gateway routes matching all 28 endpoints in the spec
- [ ] CORS preflight (`OPTIONS`) returns `200` for `localhost:5173`
- [ ] Lambda integrations resolve correctly (no `integrationUri` referencing a non-existent function)
- [ ] API Gateway access logs stream to CloudWatch

---

## WP-13 — Frontend SPA Scaffolding

**Track:** Frontend  
**Design refs:** §2 (Technology Stack)  
**Depends on:** WP-02

### Scope

Bootstrap the Vite + React + TypeScript SPA project, configure tooling, generate the TypeScript HTTP client from the OpenAPI spec, and establish the routing skeleton.

### Deliverables

| File | Description |
|---|---|
| `ui/index.html` | Vite HTML entry |
| `ui/vite.config.ts` | Vite config (dev proxy `/api` → `VITE_API_BASE_URL`) |
| `ui/package.json` | Dependencies (see below) |
| `ui/tailwind.config.ts` | Tailwind config |
| `ui/tsconfig.json` | TypeScript config |
| `ui/src/main.tsx` | React entry + `QueryClientProvider` |
| `ui/src/App.tsx` | Router (`react-router-dom`) + layout shell |
| `ui/src/api/` | Auto-generated client from OpenAPI spec (`openapi-typescript-codegen`) |

### Key Dependencies

```json
{
  "react": "^18",
  "react-dom": "^18",
  "react-router-dom": "^6",
  "@tanstack/react-query": "^5",
  "axios": "^1",
  "tailwindcss": "^3",
  "@monaco-editor/react": "^4",
  "openapi-typescript-codegen": "latest (devDependency)"
}
```

### Routes (skeleton — pages stubbed with placeholder content)

| Route | Component |
|---|---|
| `/` | `ConfigBrowser` |
| `/configs/:configId` | `ConfigEditor` |
| `/packages` | `PackageList` |
| `/packages/:packageId` | `PackageDetail` |
| `/packages/:packageId/logs` | `LogViewer` |

### `FocusBanner` Component (global)

Persistent top-of-page banner fetching `GET /configs/focus` (cached 30 s via TanStack Query). Displays: *"Config in Focus: `{name}` v`{version}`"* or *"No config in focus"* when empty.

### Acceptance Criteria

- [ ] `npm run dev` starts Vite dev server at `localhost:5173` without errors
- [ ] TypeScript client generated from `control-plane-api.yaml` with `npm run generate-api`
- [ ] All 5 routes render without runtime errors (placeholder content acceptable at this stage)
- [ ] TanStack Query `QueryClient` is correctly configured with `staleTime: 30_000`
- [ ] `FocusBanner` renders at top of every page and fetches from `GET /configs/focus`
- [ ] Tailwind utility classes apply correctly (visible styling difference between pages)

---

## WP-14 — Frontend: Config Browser & Editor

**Track:** Frontend  
**Design refs:** §2 (Pages/Routes — `/` and `/configs/:configId`)  
**Depends on:** WP-13, WP-04

### Scope

Implement the Config File Browser page and the Config Editor page with Monaco JSON editor, version history, and the "Set as Focus" and "Create Launch Package" actions.

### Deliverables

| File | Description |
|---|---|
| `ui/src/pages/ConfigBrowser.tsx` | Config list table |
| `ui/src/pages/ConfigEditor.tsx` | Monaco editor + toolbar |
| `ui/src/components/MonacoJsonEditor.tsx` | Monaco wrapper (SFC JSON schema validation) |
| `ui/src/components/FocusBanner.tsx` | Implemented (was stubbed in WP-13) |
| `ui/src/components/StatusBadge.tsx` | `active`/`archived` badge |

### `ConfigBrowser` Page

- Table columns: Name, Latest Version (ISO timestamp), Status (`StatusBadge`), Last Modified
- Click row → navigate to `/configs/:configId`
- Empty state: *"No SFC configs found — upload a config to get started"*

### `ConfigEditor` Page

- Left panel: version history list (`GET /configs/{configId}/versions`) — click to load a specific version into editor
- Main panel: `MonacoJsonEditor` with SFC JSON schema for validation and autocomplete
- Toolbar actions:
  - **Save** → `PUT /configs/{configId}` with editor content; on success, refresh version list
  - **Revert** → reload last saved version from S3 (discard unsaved edits with confirmation)
  - **Set as Focus** → `POST /configs/{configId}/focus`; `FocusBanner` refreshes automatically
  - **Create Launch Package** → navigates to `/packages` with `configId` pre-populated in creation modal

### Acceptance Criteria

- [ ] Config list loads from `GET /configs` and displays all entries
- [ ] Navigating to a config opens the latest version in Monaco editor
- [ ] Switching versions in the history panel loads the correct version content
- [ ] Save creates a new version; version list updates immediately
- [ ] "Set as Focus" updates `FocusBanner` within one poll cycle (≤ 30 s)
- [ ] Monaco editor shows JSON schema validation errors inline (red squiggle)
- [ ] Unsaved edits show a dirty indicator (`*`) in the page title

---

## WP-15 — Frontend: Package List, Detail & Log Viewer

**Track:** Frontend  
**Design refs:** §2 (Pages/Routes — `/packages`, `/packages/:packageId`, `/packages/:packageId/logs`)  
**Depends on:** WP-13, WP-06, WP-07

### Scope

Implement the Launch Package list table, package detail view (left info panel), and the paginated OTEL log viewer with severity colour-coding.

### Deliverables

| File | Description |
|---|---|
| `ui/src/pages/PackageList.tsx` | Package list table |
| `ui/src/pages/PackageDetail.tsx` | Package detail layout (left info panel + right panel placeholder for WP-16) |
| `ui/src/pages/LogViewer.tsx` | Paginated OTEL log viewer |
| `ui/src/components/OtelLogStream.tsx` | Log line renderer |

### `PackageList` Page

Table columns: Package ID (truncated + copy), Config, Config Version, Status badge (`PROVISIONING`/`READY`/`ERROR`), Live (HeartbeatStatusLed — stubbed for WP-16), Last Seen, Actions (Download, Logs, GG Export, Fix with AI).

- Auto-refresh every 10 s via TanStack Query `refetchInterval`
- Download action generates presigned URL via `GET /packages/{packageId}/download` and triggers browser download
- "Fix with AI" visible only when `status=READY`; navigates to `/packages/:packageId/logs` with error filter pre-applied

### `PackageDetail` Page

Left panel:
- Package ID, Config name, Config version
- Status badge + IoT resource ARNs (Thing name, Cert ARN, Role Alias ARN)
- Log group link → opens `LogViewer`
- "Create Greengrass Component" button (calls `POST /packages/{packageId}/greengrass`; shows component ARN on success)
- "Re-provision (new credentials)" button → `POST /packages/{packageId}/iot`

Right panel: placeholder `<PackageControlPanel />` (implemented in WP-16).

### `LogViewer` Page

- Paginated table: Timestamp, Severity chip, Body text, Resource attributes (collapsible)
- Severity colour coding: INFO = default, WARN = amber text, ERROR = red text + red left border
- Load-more pagination using `nextToken` from `GET /packages/{packageId}/logs`
- `?errorFilter=true` query param pre-selects error-only view (for "Fix with AI" entry point)
- "Fix with AI" CTA button — visible when error records present; opens remediation flow (implemented in WP-17)

### Acceptance Criteria

- [ ] Package list auto-refreshes every 10 s; new packages appear without manual reload
- [ ] Status badge transitions from `PROVISIONING` to `READY` automatically
- [ ] Download button triggers file download (not navigation)
- [ ] Log viewer paginates correctly; "Load More" fetches next page using `nextToken`
- [ ] ERROR log lines have red highlight; WARN lines have amber text
- [ ] `?errorFilter=true` pre-applies error-only filter on page load

---

## WP-16 — Frontend: Runtime Controls & Heartbeat LED

**Track:** Frontend  
**Design refs:** §2 (`PackageControlPanel.tsx`, `HeartbeatStatusLed.tsx`)  
**Depends on:** WP-13, WP-08

### Scope

Implement the `PackageControlPanel` component (telemetry/diagnostics toggles, config push, restart) and the `HeartbeatStatusLed` component (live ACTIVE/ERROR/INACTIVE indicator with recent log ticker). Both are driven by the `fn-iot-control` Lambda endpoints.

### Deliverables

| File | Description |
|---|---|
| `ui/src/components/PackageControlPanel.tsx` | Full runtime control panel |
| `ui/src/components/HeartbeatStatusLed.tsx` | LED indicator + recent logs ticker |
| `ui/src/components/ConfirmDialog.tsx` | Reusable confirmation modal |
| `ui/src/pages/PackageDetail.tsx` | Updated to include `<PackageControlPanel />` in right panel |
| `ui/src/pages/PackageList.tsx` | Updated to include `<HeartbeatStatusLed />` in Live column |

### `HeartbeatStatusLed` Behaviour

- Polls `GET /packages/{packageId}/heartbeat` every **10 seconds** via TanStack Query `refetchInterval`
- LED states:

  | Indicator | Condition |
  |---|---|
  | `● ACTIVE` (green) | `liveStatus=ACTIVE` |
  | `● ERROR` (red) | `liveStatus=ERROR` |
  | `○ INACTIVE` (grey) | `liveStatus=INACTIVE` |

- "Recent SFC output" block shows `recentLogs[0..2]` colour-coded by severity
- "Open full log viewer" link navigates to `/packages/:packageId/logs`

### `PackageControlPanel` Layout

```
Device Status
  ● ACTIVE  —  SFC running  —  Last seen: 3s ago
  [Recent SFC output block]              [Open full log viewer]

─────────────────────────────────────────────
Runtime Controls
  Telemetry (OTEL)         ● ON  ○ OFF    [Apply]
  Diagnostics (TRACE log)  ● ON  ○ OFF    [Apply]

─────────────────────────────────────────────
Push Config Update
  Config:   [dropdown]
  Version:  [dropdown]
             [Push Update]

─────────────────────────────────────────────
Restart SFC Runtime                  [Restart ↺]
Last restart: 2026-02-24 14:32 UTC
```

- Initial state loaded from `GET /packages/{packageId}/control`
- "Apply" button shows spinner then ✓ tick on success
- Config dropdown populated from `GET /configs`; version dropdown from `GET /configs/{configId}/versions`
- **Restart** requires `<ConfirmDialog />` before firing `POST .../control/restart`
- All controls disabled with tooltip *"Package must be in READY state"* when `status != READY`

### `ConfirmDialog` Component

Reusable modal with `title`, `message`, `onConfirm`, `onCancel` props. Used by the Restart action.

### Acceptance Criteria

- [ ] LED updates within 10 s of `sfcRunning` state change
- [ ] Toggle "Apply" fires correct endpoint and updates local state optimistically
- [ ] Config version dropdown cascades correctly (version list reloads when config selection changes)
- [ ] Restart button shows `ConfirmDialog`; cancel does not fire the endpoint
- [ ] All controls are visually disabled and show tooltip when `status != READY`
- [ ] `GET .../control` pre-populates toggle states on panel mount

---

## WP-17 — Frontend: AI Remediation UI

**Track:** Frontend  
**Design refs:** §2 (Log Viewer CTA), §9  
**Depends on:** WP-13, WP-10, WP-15

### Scope

Implement the AI remediation trigger flow, side-by-side config diff view, and the single-click "Create New Launch Package" CTA that closes the error-to-fix loop.

### Deliverables

| File | Description |
|---|---|
| `ui/src/pages/LogViewer.tsx` | Updated: "Fix with AI" CTA wired to remediation call |
| `ui/src/pages/PackageDetail.tsx` | Updated: lineage chain display (`sourcePackageId`) |
| `ui/src/components/RemediationDiffView.tsx` | Side-by-side diff viewer (old config vs. corrected config) |

### Remediation Flow (UI)

1. User clicks **"Fix with AI"** in `LogViewer` — button visible when error records are present
2. Modal opens: date-range picker pre-populated with the error time window (from filtered log records)
3. User clicks **"Analyse with AI"** → `POST /packages/{packageId}/remediate` with `errorWindowStart`/`errorWindowEnd`
4. Loading spinner shown during 120 s max wait
5. On success: `<RemediationDiffView>` renders side-by-side old config (left) vs. corrected config (right); changed lines highlighted
6. Primary CTA: **"Create New Launch Package with Corrected Config"** → `POST /packages` with `newConfigVersion` pre-selected; navigates to `/packages` on success
7. Secondary action: **"Save Config Only"** → saves corrected config as new version without creating a package

### `RemediationDiffView` Component

- Left panel: original `sfc-config.json` (read-only Monaco)
- Right panel: corrected config (read-only Monaco, changed lines highlighted in green)
- Summary banner: *"AI found and corrected N issues. Review the changes below."*
- Both panels share line numbers for easy comparison

### Package Lineage Display (in `PackageDetail`)

When `sourcePackageId` is set on a package, show a lineage breadcrumb:

```
📦 Original: abc-123  →  ✦ AI-remediated: def-456 (current)
```

Clicking the original package ID navigates to its detail page.

### Acceptance Criteria

- [ ] "Fix with AI" button appears in `LogViewer` only when error-severity records are present
- [ ] Time window pre-populated from first and last ERROR record timestamps
- [ ] Loading state prevents double-submit during AgentCore invocation
- [ ] `RemediationDiffView` correctly highlights changed JSON lines in both panels
- [ ] "Create New Launch Package" calls `POST /packages` with `newConfigVersion` (not latest focus)
- [ ] New package created from remediation has `sourcePackageId` set; lineage breadcrumb visible in `PackageDetail`
- [ ] Error response from `fn-agent-remediate` (e.g. `504`) shows user-friendly error toast

---

## WP-18 — CloudFront + S3 UI Hosting CDK Construct

**Track:** Infrastructure  
**Design refs:** §5, §11 (`ui_hosting.py`), §12 (Security)  
**Depends on:** WP-01, WP-12

### Scope

Implement the `SfcCloudFrontDistribution` CDK construct: CloudFront distribution with two origins (S3 `ui/` prefix for SPA static files via OAC, API Gateway for `/api/*`), bucket policy, and HTTPS-only enforcement.

### Deliverables

| File | Description |
|---|---|
| `cdk/constructs/ui_hosting.py` | `UiHosting` CDK construct |
| `cdk/sfc_agent_stack.py` | Import and instantiate `UiHosting`; pass `SfcConfigBucket` + `HttpApi` references |

### CloudFront Configuration

| Setting | Value |
|---|---|
| Default origin | `SfcConfigBucket/ui/` (S3, OAC) |
| `/api/*` behaviour | API Gateway HTTP API URL (no cache, forward all headers) |
| Viewer protocol | `HTTPS_ONLY` |
| Cache policy (default) | `CachingOptimized` |
| Cache policy (`/api/*`) | `CachingDisabled` |
| Price class | `PriceClass.PRICE_CLASS_100` |
| Default root object | `index.html` |
| Custom error responses | `403` → `200` `/index.html` (SPA client-side routing) |

### OAC Bucket Policy (added to `SfcConfigBucket`)

```json
{
  "Effect": "Allow",
  "Principal": { "Service": "cloudfront.amazonaws.com" },
  "Action": "s3:GetObject",
  "Resource": "arn:aws:s3:::{SfcConfigBucket}/ui/*",
  "Condition": {
    "StringEquals": {
      "AWS:SourceArn": "arn:aws:cloudfront::{account}:distribution/{distributionId}"
    }
  }
}
```

- `BlockPublicAccess`: all four settings remain enabled
- No `Principal: *` in bucket policy

### CDK Outputs

| Output | Value |
|---|---|
| `SfcControlPlaneUiUrl` | `https://{distribution.domain_name}` |

### Acceptance Criteria

- [ ] `cdk synth` produces CloudFront distribution with OAC (not OAI)
- [ ] Direct S3 URL returns `403`; CloudFront URL returns `200` for `ui/index.html`
- [ ] HTTP → HTTPS redirect works at CloudFront viewer level
- [ ] SPA deep links (e.g. `/packages/abc-123`) return `index.html` (custom error response `403 → 200`)
- [ ] `/api/*` requests are forwarded to API Gateway without caching
- [ ] `BlockPublicAccess` remains fully enabled on `SfcConfigBucket` after deployment

---

## WP-19 — Integration & End-to-End Validation

**Track:** Validation  
**Design refs:** All  
**Depends on:** WP-01 through WP-18

### Scope

Validate all major flows end-to-end against a deployed stack. Covers the primary operator workflow, AI remediation path, heartbeat LED lifecycle, control channel round-trip, and local development setup.

### Test Scenarios

#### Scenario A — Primary Operator Flow

1. Deploy CDK stack; navigate to CloudFront UI URL
2. Upload a new SFC config via Monaco editor → verify `PUT /configs/{configId}` creates DDB record + S3 object
3. Set config as focus → verify `FocusBanner` updates
4. Create Launch Package → verify `status` transitions `PROVISIONING → READY`
5. Download zip → verify zip is valid and contains all required files
6. Extract zip; launch `runner.py` on a test host → verify SFC starts and OTEL logs appear in CloudWatch
7. Verify heartbeat LED shows `● ACTIVE` within 15 s in the UI

#### Scenario B — Runtime Control Round-trip

1. Toggle telemetry OFF via `PackageControlPanel` → verify `PUT .../control/telemetry {"enabled": false}` fires
2. Verify IoT MQTT message received by edge agent (check agent logs)
3. Verify OTEL log delivery to CloudWatch stops
4. Toggle telemetry ON → verify CloudWatch log delivery resumes
5. Push a config update → verify edge agent downloads and applies new config
6. Trigger restart → verify `ConfirmDialog` shown; confirm; verify SFC subprocess restarts (heartbeat `sfcPid` changes)

#### Scenario C — AI Remediation Path

1. Inject deliberate error into SFC config (e.g. invalid OPC-UA node ID)
2. Wait for ERROR-severity OTEL records to appear in CloudWatch (≥ 2 records)
3. Click "Fix with AI" in Log Viewer → verify `POST .../remediate` fires with correct `errorWindowStart`/`errorWindowEnd`
4. Verify `RemediationDiffView` renders with corrected config
5. Click "Create New Launch Package" → verify new package record with `sourcePackageId` set
6. Verify lineage breadcrumb appears in `PackageDetail` for the new package
