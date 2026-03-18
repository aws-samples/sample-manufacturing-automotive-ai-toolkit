TODO
====


## Edge
- [x] heartbeat not sent - not received in iot core - shall lead to Status Active in LP view
- [x] config update shall only be possible with new versions of the Launch package's existing config...
- [x] config-update does not work - presigned s3 url not found
- [x] Logs shall be tailed in near-real time (check ERROR filter)
- [x] Telemetry / Diagnostics toggles
- [x] Add one-click UI macOS/linux/windows runners to Launch Package
- [x] Fix sfc path length issue by using java jar based runtime
- [x] Remove Java installer if java not found
- [x] Fix Dockerfile & docker build script - add instructions to LP README.md
- [x] Make sure that the [SFC top-level Metrics adapter](https://github.com/awslabs/industrial-shopfloor-connect/blob/main/docs/core/sfc-configuration.md#metrics) is always built into a LP's config
- [ ] Trace logs switch and switch back leads to logging disappear - subprocess fix required.

## Control Plane
- [x] AI Remidiation
- [x] AI remediation shall not update Launch packages config - just use the remediated config and create new versions of the LP's config
- [x] Config Versioning - use iterations like v1, v2 etc. instead of Timestamp
- [x] SFC Cloudwatch Metrics dashboard
- [x] Log Viewer & API calls only 100 oldest log lines - not newest
- [x] AI guided "Create config" option with prompt & file upload to context (instant base64 encoding)
- [x] AI guided config Update option
- [x] Detect Agentic Summary response & show proper html instead of json editor
- [ ] Add token based auth to APIGW & UX
- [ ] Add UI-pagination
- [x] Check if GG comp creation works
- [ ] Create AgentCore Gateway - facading the SFC Control Plane HTTP API
- [x] Add Tag Mapping Tools for importing existing PLC docs (text only) and creating SFC Channel Maps
