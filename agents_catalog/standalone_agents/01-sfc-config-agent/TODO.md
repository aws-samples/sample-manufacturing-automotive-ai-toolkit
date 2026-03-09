TODO:

## Edge
[ x ] heartbeat not sent - not received in iot core - shall lead to Status Active in LP view
[ x ] config update shall only be possible with new versions of the Launch package's existing config...
[ x ] config-update does not work - presigned s3 url not found
[   ] Logs shall be tailed in near-real time (check ERROR filter)
[   ] Telemetry / Diagnostics toggles
[   ] Add one-click UI macOS/linux/windows runners to Launch Package
[   ] Fix sfc path length issue by using java jar based runtime

## Control Plane
[   ] AI Remidiation
[   ] Viz based on Telemetry
[   ] Cloudwatch Metrics
[   ] Log Viewer & API calls only 100 oldest log lines - not newest
[ x ] AI guided "Create config" option with prompt & file upload to context (instant base64 encoding)
[   ] Only "high level validated" configs shall be eligible to be in in Focus -> Launch Configs
[   ] Detect Agentic Summary response & show proper html instead of json editor
[   ] Add token based auth to APIGW & UX
[   ] Add UI-pagination