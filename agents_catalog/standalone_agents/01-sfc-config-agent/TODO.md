TODO:

## Edge
[ x ] heartbeat not sent - not received in iot core - shall lead to Status Active in LP view
[ x ] config update shall only be possible with new versions of the Launch package's existing config...
[ x ] config-update does not work - presigned s3 url not found
[ x ] Logs shall be tailed in near-real time (check ERROR filter)
[   ] Telemetry / Diagnostics toggles
[   ] Add one-click UI macOS/linux/windows runners to Launch Package
[   ] Fix sfc path length issue by using java jar based runtime
[   ] Remove Java installer if java not found

## Control Plane
[ x ] AI Remidiation
[ x ] AI remediation shall not update Launch packages config - just use the remediated config and create new versions of the LP's config
[ x ] Config Versioning - use iterations like v1, v2 etc. instead of Timestamp 
[   ] Viz based on TelemetryR
[   ] Cloudwatch Metrics
[ x ] Log Viewer & API calls only 100 oldest log lines - not newest
[ x ] AI guided "Create config" option with prompt & file upload to context (instant base64 encoding)
[ x ] AI guided config Update option
[ x ] Detect Agentic Summary response & show proper html instead of json editor
[   ] Add token based auth to APIGW & UX
[   ] Add UI-pagination
[   ] Check if GG comp creation works