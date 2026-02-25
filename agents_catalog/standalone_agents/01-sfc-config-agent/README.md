# SFC Config Generation Agent

AI-powered **Shop Floor Connectivity (SFC)** configuration assistant — create, validate, and remediate SFC configs via natural language, then deploy them as self-contained edge packages from the Control Plane UI.

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

echo  '{"prompt": "Create an OPC-UA SFC config for a press machine with two data sources"}' > input.json

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
| `AgentCoreMemoryId` | Short-term memory ID (also in SSM `/sfc-config-agent/memory-id`) |

See the repository-level [deployment guide](../../../docs/deployment.md) for full instructions.

---

## Project Structure

```
01-sfc-config-agent/
├── manifest.json
├── requirements.txt
├── cdk/
│   ├── stack.py                       # CDK stack
│   ├── control-plane-design.md        # Architecture design document
│   ├── openapi/control-plane-api.yaml # API spec (source of truth for API GW)
│   └── constructs/                    # CDK constructs per subsystem
├── src/
│   ├── agent.py                       # AgentCore entry-point
│   ├── sfc-spec-mcp-server.py         # MCP server (SFC spec validation tools)
│   ├── lambda_handlers/               # Control Plane Lambda functions
│   └── layer/sfc_cp_utils/            # Shared Lambda layer (DDB, S3, IoT helpers)
└── ui/                                # Vite + React control plane SPA
    └── src/
        ├── pages/                     # ConfigBrowser, ConfigEditor, PackageList, LogViewer
        └── components/                # MonacoJsonEditor, HeartbeatStatusLed, PackageControlPanel