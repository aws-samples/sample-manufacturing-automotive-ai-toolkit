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
  diagnosticsEnabled: boolean;
  lastConfigUpdateAt?: string;
  lastConfigUpdateVersion?: string;
  lastRestartAt?: string;
}

export interface LogEvent {
  /** ISO-8601 timestamp string (e.g. "2026-02-27T16:34:12.451000+00:00") */
  timestamp: string;
  /** SFC-native log level extracted from the log body */
  severityText: "TRACE" | "INFO" | "WARNING" | "ERROR";
  severityNumber: number;
  body: string;
}

export interface LogsResponse {
  records: LogEvent[];
  nextToken?: string;
}

export interface RemediationResponse {
  sessionId: string;
  status: "PENDING" | "COMPLETE" | "FAILED";
  newConfigVersion?: string;
  correctedConfig?: Record<string, unknown>;
  error?: string;
}

export interface GenerateConfigRequest {
  name: string;
  description?: string;
  /** One or more SFC protocol adapter ids, e.g. ["OPCUA", "Modbus TCP"] */
  protocol_adapters: string[];
  /** Free-text connection strings / endpoint URLs (one per line or list item) */
  source_endpoints: string[];
  /** One or more SFC target ids, e.g. ["AWS IoT Core", "Debug"] */
  sfc_targets: string[];
  channels_description: string;
  sampling_interval_ms: number;
  additional_context?: string;
  /** AI-extracted + user-confirmed tag mappings per adapter (from "Bring your Tags") */
  tag_mappings?: TagMapping[];
}

/** Returned immediately by POST /configs/generate (202 Accepted) */
export interface GenerateConfigJobAccepted {
  jobId: string;
  status: "PENDING";
}

/** Returned by GET /configs/generate/{jobId} */
export interface GenerateConfigJobStatus {
  jobId: string;
  status: "PENDING" | "COMPLETE" | "FAILED";
  configId?: string;
  version?: string;
  name?: string;
  error?: string;
}

/** Kept for backwards compat — shape returned when job is COMPLETE */
export interface GenerateConfigResponse {
  configId: string;
  version: string;
  name: string;
}

// ─── Config endpoints ────────────────────────────────────────────────────────

export const listConfigs = () =>
  api.get<{ configs: ConfigItem[] }>("/configs").then((r) => r.data.configs ?? []);

export const getConfig = (configId: string) =>
  api.get<ConfigItem & { content?: string }>(`/configs/${configId}`).then((r) => r.data);

export const listConfigVersions = (configId: string) =>
  api.get<{ versions: ConfigItem[] }>(`/configs/${configId}/versions`).then((r) => r.data.versions ?? []);

export const getConfigVersion = (configId: string, version: string) =>
  api
    .get<ConfigItem & { content: string }>(
      `/configs/${configId}/versions/${encodeURIComponent(version)}`
    )
    .then((r) => r.data);

export const saveConfig = (
  configId: string,
  body: { name: string; description?: string; content: string; tags?: string[] }
) => {
  let parsedContent: unknown;
  try {
    parsedContent = JSON.parse(body.content);
  } catch {
    parsedContent = {};
  }
  return api
    .put<ConfigItem>(`/configs/${configId}`, { ...body, content: parsedContent })
    .then((r) => r.data);
};

export const createConfig = (body: {
  name: string;
  description?: string;
  content: string;
}) => {
  let parsedContent: unknown;
  try {
    parsedContent = JSON.parse(body.content);
  } catch {
    parsedContent = {};
  }
  return api
    .post<ConfigItem>("/configs", { ...body, content: parsedContent })
    .then((r) => r.data);
};

export const getFocus = () =>
  api.get<FocusState>("/configs/focus").then((r) => r.data);

export const setFocus = (configId: string, version: string) =>
  api
    .post<FocusState>(`/configs/${configId}/focus`, { version })
    .then((r) => r.data);

export const clearFocus = () =>
  api.delete<FocusState>("/configs/focus").then((r) => r.data);

export const deleteConfig = (configId: string) =>
  api.delete<{ message: string }>(`/configs/${configId}`).then((r) => r.data);

// ─── Package endpoints ───────────────────────────────────────────────────────

export const listPackages = () =>
  api.get<{ packages: LaunchPackage[] }>("/packages").then((r) => r.data.packages ?? []);

export const getPackage = (packageId: string) =>
  api.get<LaunchPackage>(`/packages/${packageId}`).then((r) => r.data);

export const createPackage = (body: {
  configId: string;
  configVersion: string;
  region?: string;
  sourcePackageId?: string;
}) => api.post<LaunchPackage>("/packages", body).then((r) => r.data);

export const deletePackage = (packageId: string) =>
  api.delete(`/packages/${packageId}`).then((r) => r.data);

export const deepDeletePackage = (packageId: string) =>
  api.delete(`/packages/${packageId}?deep=true`).then((r) => r.data);

export const updatePackageTags = (packageId: string, tags: string[]) =>
  api.patch<{ tags: string[] }>(`/packages/${packageId}/tags`, { tags }).then((r) => r.data);

export const updateConfigTags = (configId: string, tags: string[]) =>
  api.patch<{ tags: string[] }>(`/configs/${configId}/tags`, { tags }).then((r) => r.data);

export const getPackageDownloadUrl = (packageId: string) =>
  api
    .get<{ downloadUrl: string }>(`/packages/${packageId}/download`)
    .then((r) => r.data.downloadUrl);

// ─── Logs endpoints ──────────────────────────────────────────────────────────

export const getLogs = (
  packageId: string,
  params: {
    startTime?: string;
    endTime?: string;
    nextToken?: string;
    limit?: number;
    lookbackMinutes?: number;
    errorsOnly?: boolean;
  } = {}
) =>
  api
    .get<LogsResponse>(
      `/packages/${packageId}/logs${params.errorsOnly ? "/errors" : ""}`,
      { params }
    )
    .then((r) => r.data);

// ─── Control endpoints ───────────────────────────────────────────────────────

export const getControlState = (packageId: string) =>
  api
    .get<ControlState>(`/packages/${packageId}/control`)
    .then((r) => r.data);

export const setDiagnostics = (packageId: string, enabled: boolean) =>
  api
    .put(`/packages/${packageId}/control/diagnostics`, { enabled })
    .then((r) => r.data);

export const pushConfigUpdate = (
  packageId: string,
  configId: string,
  configVersion: string
) =>
  api
    .post(`/packages/${packageId}/control/config-update`, {
      configId,
      configVersion,
    })
    .then((r) => r.data);

export const restartSfc = (packageId: string) =>
  api
    .post(`/packages/${packageId}/control/restart`, {})
    .then((r) => r.data);

export const getHeartbeat = (packageId: string) =>
  api
    .get<HeartbeatStatus>(`/packages/${packageId}/heartbeat`)
    .then((r) => r.data);

// ─── Greengrass endpoints ────────────────────────────────────────────────────

export const createGgComponent = (packageId: string) =>
  api
    .post<{ ggComponentArn: string }>(`/packages/${packageId}/greengrass`)
    .then((r) => r.data);

export const getGgComponent = (packageId: string) =>
  api
    .get<{ ggComponentArn?: string; deploymentStatus?: string }>(
      `/packages/${packageId}/greengrass`
    )
    .then((r) => r.data);

// ─── AI-guided config generation endpoint (async) ────────────────────────────

/** POST /configs/generate → 202 { jobId } */
export const startGenerateConfig = (body: GenerateConfigRequest) =>
  api
    .post<GenerateConfigJobAccepted>("/configs/generate", body)
    .then((r) => r.data);

/** GET /configs/generate/{jobId} → job status */
export const pollGenerateConfig = (jobId: string) =>
  api
    .get<GenerateConfigJobStatus>(`/configs/generate/${encodeURIComponent(jobId)}`)
    .then((r) => r.data);

/**
 * Convenience: start generation and poll until COMPLETE or FAILED.
 * Calls onPending on every pending poll (optional).
 * Resolves with the completed job or rejects on FAILED/timeout.
 */
export const generateConfig = async (
  body: GenerateConfigRequest,
  opts: { pollIntervalMs?: number; timeoutMs?: number; onPending?: () => void } = {}
): Promise<GenerateConfigJobStatus> => {
  const { pollIntervalMs = 5000, timeoutMs = 360_000, onPending } = opts;
  const { jobId } = await startGenerateConfig(body);
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, pollIntervalMs));
    const status = await pollGenerateConfig(jobId);
    if (status.status === "COMPLETE") return status;
    if (status.status === "FAILED")
      throw new Error(status.error ?? "AI config generation failed");
    onPending?.();
  }
  throw new Error("AI config generation timed out");
};

// ─── Tag extraction ──────────────────────────────────────────────────────────

export interface ExtractedTag {
  address: string;
  name: string;
  dataType: string;
  description?: string;
}

export interface ExtractedEndpoint {
  ip: string | null;
  port: string | null;
  description?: string;
}

export interface ExtractedPlc {
  plcId: string;
  endpoint: ExtractedEndpoint | null;
  tags: ExtractedTag[];
}

export interface TagExtractResponse {
  plcs: ExtractedPlc[];
}

/** Tag mapping entry attached to a generate request (selected tags per adapter). */
export interface TagMapping {
  adapterId: string;
  plcs: Array<{
    plcId: string;
    endpoint: ExtractedEndpoint | null;
    /** Only the addresses the user ticked */
    selectedTags: ExtractedTag[];
  }>;
}

export const extractTags = (protocol: string, docText: string) =>
  api
    .post<TagExtractResponse>("/configs/tags/extract", { protocol, docText })
    .then((r) => r.data);

// ─── Metrics endpoints ───────────────────────────────────────────────────────

export type MetricsCategory = "Target" | "Core" | "Adapter" | "All";

export interface ChartJsDataPoint {
  x: string; // ISO-8601 UTC timestamp
  y: number;
}

export interface ChartJsDataset {
  label: string;
  data: ChartJsDataPoint[];
  borderColor: string;
  backgroundColor: string;
  tension: number;
  fill: boolean;
  pointRadius: number;
}

export const getPackageMetrics = (
  packageId: string,
  category: MetricsCategory = "Target",
  lookbackMinutes = 15
) =>
  api
    .post<ChartJsDataset[]>(`/packages/${packageId}/metrics`, {
      category,
      lookbackMinutes,
    })
    .then((r) => r.data);

// ─── Remediation endpoints ───────────────────────────────────────────────────

export const triggerRemediation = (
  packageId: string,
  errorWindowStart: string,
  errorWindowEnd: string,
  selectedErrors?: string[]
) =>
  api
    .post<RemediationResponse>(`/packages/${packageId}/remediate`, {
      errorWindowStart,
      errorWindowEnd,
      ...(selectedErrors !== undefined ? { selectedErrors } : {}),
    })
    .then((r) => r.data);

export const pollRemediation = (packageId: string, sessionId: string) =>
  api
    .get<RemediationResponse>(
      `/packages/${packageId}/remediate/${encodeURIComponent(sessionId)}`
    )
    .then((r) => r.data);
