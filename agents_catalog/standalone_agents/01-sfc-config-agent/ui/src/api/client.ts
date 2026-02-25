import axios from "axios";

const BASE_URL =
  (import.meta as unknown as { env: Record<string, string> }).env
    .VITE_API_BASE_URL ?? "";

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// ─── Types ──────────────────────────────────────────────────────────────────

export interface ConfigItem {
  configId: string;
  version: string;
  name: string;
  description?: string;
  s3Key?: string;
  status: "active" | "archived";
  createdAt: string;
}

export interface FocusState {
  focusedConfigId?: string;
  focusedConfigVersion?: string;
  updatedAt?: string;
}

export interface LaunchPackage {
  packageId: string;
  createdAt: string;
  configId: string;
  configVersion: string;
  status: "PROVISIONING" | "READY" | "ERROR";
  iotThingName?: string;
  iotCertArn?: string;
  iotRoleAliasArn?: string;
  iamRoleArn?: string;
  s3ZipKey?: string;
  logGroupName?: string;
  ggComponentArn?: string;
  sourcePackageId?: string;
  telemetryEnabled?: boolean;
  diagnosticsEnabled?: boolean;
  lastConfigUpdateAt?: string;
  lastConfigUpdateVersion?: string;
  lastRestartAt?: string;
  lastHeartbeatAt?: string;
  sfcRunning?: boolean;
}

export interface HeartbeatStatus {
  packageId: string;
  lastHeartbeatAt?: string;
  sfcRunning: boolean;
  recentLogs: string[];
  liveStatus: "ACTIVE" | "ERROR" | "INACTIVE";
}

export interface ControlState {
  packageId: string;
  telemetryEnabled: boolean | "unknown";
  diagnosticsEnabled: boolean | "unknown";
  lastConfigUpdateAt?: string;
  lastConfigUpdateVersion?: string;
  lastRestartAt?: string;
}

export interface LogEvent {
  timestamp: number;
  message: string;
  ingestionTime?: number;
}

export interface LogsResponse {
  events: LogEvent[];
  nextToken?: string;
}

export interface RemediationResponse {
  sessionId: string;
  newConfigVersion: string;
  correctedConfig: Record<string, unknown>;
}

// ─── Config endpoints ────────────────────────────────────────────────────────

export const listConfigs = () =>
  api.get<ConfigItem[]>("/api/configs").then((r) => r.data);

export const getConfig = (configId: string) =>
  api.get<ConfigItem & { content?: string }>(`/api/configs/${configId}`).then((r) => r.data);

export const listConfigVersions = (configId: string) =>
  api.get<ConfigItem[]>(`/api/configs/${configId}/versions`).then((r) => r.data);

export const getConfigVersion = (configId: string, version: string) =>
  api
    .get<ConfigItem & { content: string }>(
      `/api/configs/${configId}/versions/${encodeURIComponent(version)}`
    )
    .then((r) => r.data);

export const saveConfig = (
  configId: string,
  body: { name: string; description?: string; content: string }
) => api.put<ConfigItem>(`/api/configs/${configId}`, body).then((r) => r.data);

export const createConfig = (body: {
  name: string;
  description?: string;
  content: string;
}) => api.post<ConfigItem>("/api/configs", body).then((r) => r.data);

export const getFocus = () =>
  api.get<FocusState>("/api/configs/focus").then((r) => r.data);

export const setFocus = (configId: string, version: string) =>
  api
    .post<FocusState>(`/api/configs/${configId}/focus`, { version })
    .then((r) => r.data);

// ─── Package endpoints ───────────────────────────────────────────────────────

export const listPackages = () =>
  api.get<LaunchPackage[]>("/api/packages").then((r) => r.data);

export const getPackage = (packageId: string) =>
  api.get<LaunchPackage>(`/api/packages/${packageId}`).then((r) => r.data);

export const createPackage = (body: {
  configId: string;
  configVersion: string;
  region?: string;
  sourcePackageId?: string;
}) => api.post<LaunchPackage>("/api/packages", body).then((r) => r.data);

export const deletePackage = (packageId: string) =>
  api.delete(`/api/packages/${packageId}`).then((r) => r.data);

export const getPackageDownloadUrl = (packageId: string) =>
  api
    .get<{ url: string }>(`/api/packages/${packageId}/download`)
    .then((r) => r.data.url);

// ─── Logs endpoints ──────────────────────────────────────────────────────────

export const getLogs = (
  packageId: string,
  params: {
    startTime?: string;
    endTime?: string;
    nextToken?: string;
    limit?: number;
    errorsOnly?: boolean;
  } = {}
) =>
  api
    .get<LogsResponse>(
      `/api/packages/${packageId}/logs${params.errorsOnly ? "/errors" : ""}`,
      { params }
    )
    .then((r) => r.data);

// ─── Control endpoints ───────────────────────────────────────────────────────

export const getControlState = (packageId: string) =>
  api
    .get<ControlState>(`/api/packages/${packageId}/control`)
    .then((r) => r.data);

export const setTelemetry = (packageId: string, enabled: boolean) =>
  api
    .put(`/api/packages/${packageId}/control/telemetry`, { enabled })
    .then((r) => r.data);

export const setDiagnostics = (packageId: string, enabled: boolean) =>
  api
    .put(`/api/packages/${packageId}/control/diagnostics`, { enabled })
    .then((r) => r.data);

export const pushConfigUpdate = (
  packageId: string,
  configId: string,
  configVersion: string
) =>
  api
    .post(`/api/packages/${packageId}/control/config-update`, {
      configId,
      configVersion,
    })
    .then((r) => r.data);

export const restartSfc = (packageId: string) =>
  api
    .post(`/api/packages/${packageId}/control/restart`, {})
    .then((r) => r.data);

export const getHeartbeat = (packageId: string) =>
  api
    .get<HeartbeatStatus>(`/api/packages/${packageId}/heartbeat`)
    .then((r) => r.data);

// ─── Greengrass endpoints ────────────────────────────────────────────────────

export const createGgComponent = (packageId: string) =>
  api
    .post<{ ggComponentArn: string }>(`/api/packages/${packageId}/greengrass`)
    .then((r) => r.data);

export const getGgComponent = (packageId: string) =>
  api
    .get<{ ggComponentArn?: string; deploymentStatus?: string }>(
      `/api/packages/${packageId}/greengrass`
    )
    .then((r) => r.data);

// ─── Remediation endpoints ───────────────────────────────────────────────────

export const triggerRemediation = (
  packageId: string,
  errorWindowStart: string,
  errorWindowEnd: string
) =>
  api
    .post<RemediationResponse>(`/api/packages/${packageId}/remediate`, {
      errorWindowStart,
      errorWindowEnd,
    })
    .then((r) => r.data);

export const pollRemediation = (packageId: string, sessionId: string) =>
  api
    .get<RemediationResponse>(
      `/api/packages/${packageId}/remediate/${encodeURIComponent(sessionId)}`
    )
    .then((r) => r.data);