import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { generateConfig, type GenerateConfigJobStatus } from "../api/client";
import MarkdownRenderer from "./MarkdownRenderer";

// ─── SFC Protocol Adapters (source side) ─────────────────────────────────────

const SFC_ADAPTERS = [
  { id: "OPCUA",      label: "OPC-UA",             desc: "OPC Unified Architecture"           },
  { id: "Modbus",     label: "Modbus TCP",          desc: "Modbus TCP/IP industrial standard"  },
  { id: "MQTT",       label: "MQTT",                desc: "Pub/sub IoT messaging"              },
  { id: "S7",         label: "S7 / Siemens",        desc: "S7-300/400/1200/1500 native"        },
  { id: "OPCDA",      label: "OPC-DA",              desc: "Legacy Windows OPC Data Access"     },
  { id: "PCCC",       label: "PCCC / Allen-Bradley", desc: "Rockwell / Allen-Bradley PLCs"     },
  { id: "SLMP",       label: "SLMP / Melsec",       desc: "Mitsubishi Seamless Message Proto." },
  { id: "ADS",        label: "ADS / Beckhoff",      desc: "TwinCAT / Beckhoff PLCs"            },
  { id: "J1939",      label: "J1939",               desc: "Heavy-duty vehicle CAN bus"         },
  { id: "SNMP",       label: "SNMP",                desc: "Network device management"          },
  { id: "REST",       label: "REST",                desc: "HTTP GET from RESTful endpoints"    },
  { id: "SQL",        label: "SQL",                 desc: "JDBC relational database queries"   },
  { id: "NATS",       label: "NATS",                desc: "Cloud-native NATS messaging"        },
  { id: "Simulator",  label: "Simulator",           desc: "Synthetic data for testing"         },
];

// ─── SFC Targets (destination side) ──────────────────────────────────────────

const SFC_TARGETS_SERVICE = [
  { id: "AWS-IOT-CORE",         label: "AWS IoT Core",        desc: "Managed IoT device connectivity"    },
  { id: "AWS-SITEWISE",         label: "AWS SiteWise",        desc: "Industrial equipment data at scale" },
  { id: "AWS-S3",               label: "AWS S3",              desc: "Object storage"                     },
  { id: "AWS-S3-TABLES",        label: "S3 Tables (Iceberg)", desc: "Iceberg tables on S3"               },
  { id: "AWS-MSK",              label: "AWS MSK (Kafka)",     desc: "Managed Kafka"                      },
  { id: "AWS-KINESIS",          label: "Kinesis Streams",     desc: "Real-time data streaming"           },
  { id: "AWS-FIREHOSE",         label: "Kinesis Firehose",    desc: "Streaming delivery"                 },
  { id: "AWS-LAMBDA",           label: "AWS Lambda",          desc: "Event-driven serverless compute"    },
  { id: "AWS-SNS",              label: "AWS SNS",             desc: "Pub/sub notifications"              },
  { id: "AWS-SQS",              label: "AWS SQS",             desc: "Managed message queue"              },
];

const SFC_TARGETS_LOCAL = [
  { id: "DEBUG-TARGET",             label: "Debug",          desc: "Console output for local testing"    },
  { id: "MQTT-TARGET",                     label: "MQTT (local)",   desc: "MQTT broker target"                  },
  { id: "NATS-TARGET",                     label: "NATS (local)",   desc: "NATS messaging target"               },
  { id: "FILE-TARGET",                     label: "File",           desc: "Write to local filesystem"           },
  { id: "OPCUA-TARGET",             label: "OPC-UA Server",  desc: "Expose data via OPC-UA server"       },
  { id: "OPCUA-WRITER-TARGET",      label: "OPC-UA Writer",  desc: "Write to external OPC-UA nodes"      },
  { id: "AWS-SITEWISEEDGE-TARGET",  label: "SiteWise Edge",  desc: "Local SiteWise edge processing"      },
];

// ─── Helpers to detect adapters / targets from existing config ────────────────

/**
 * Inspect the top-level AdapterTypes section of an SFC config and return all
 * adapter ids that match a known SFC_ADAPTERS entry.
 *
 * AdapterTypes keys are exact SFC constants (e.g. "OPCUA", "Modbus", "S7"),
 * so a straightforward case-insensitive equality check against our known ids
 * is sufficient — no fuzzy matching needed.
 */
function detectAdapters(cfg: Record<string, unknown>): string[] {
  const found = new Set<string>();
  const adapterTypes = cfg["AdapterTypes"];
  if (adapterTypes && typeof adapterTypes === "object" && !Array.isArray(adapterTypes)) {
    for (const key of Object.keys(adapterTypes as Record<string, unknown>)) {
      const match = SFC_ADAPTERS.find(
        (a) => a.id.toLowerCase() === key.toLowerCase()
      );
      if (match) found.add(match.id);
    }
  }
  return Array.from(found);
}

/**
 * Inspect the top-level TargetTypes section of an SFC config and return all
 * target ids that match a known SFC_TARGETS_SERVICE / SFC_TARGETS_LOCAL entry.
 *
 * TargetTypes keys are exact SFC constants (e.g. "AWS-IOT-CORE", "DEBUG"),
 * so a straightforward case-insensitive equality check against our known ids
 * is sufficient — no fuzzy matching needed.
 */
function detectTargets(cfg: Record<string, unknown>): string[] {
  const found = new Set<string>();
  const targetTypes = cfg["TargetTypes"];
  if (targetTypes && typeof targetTypes === "object" && !Array.isArray(targetTypes)) {
    const allTargets = [...SFC_TARGETS_SERVICE, ...SFC_TARGETS_LOCAL];
    for (const key of Object.keys(targetTypes as Record<string, unknown>)) {
      const match = allTargets.find(
        (t) => t.id.toLowerCase() === key.toLowerCase()
      );
      if (match) found.add(match.id);
    }
  }
  return Array.from(found);
}

/**
 * Build initial WizardState from an existing SFC config JSON.
 */
function buildUpdateWizardState(
  cfg: Record<string, unknown>,
  currentConfigName: string
): WizardState {
  const detectedAdapters = detectAdapters(cfg);
  const detectedTargets = detectTargets(cfg);
  return {
    name: currentConfigName,
    description: (cfg["Description"] as string | undefined) ?? "",
    protocol_adapters: detectedAdapters.length > 0 ? detectedAdapters : ["OPCUA"],
    source_endpoints: "",
    sfc_targets: detectedTargets.length > 0 ? detectedTargets : ["DEBUG-TARGET"],
    channels_description: "",
    additional_context: "",
  };
}

// ─── Wizard state ─────────────────────────────────────────────────────────────

type WizardStep = 1 | 2 | 3 | 4 | 5;

interface WizardState {
  name: string;
  description: string;
  protocol_adapters: string[];
  source_endpoints: string;
  sfc_targets: string[];
  channels_description: string;
  additional_context: string;
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface AiConfigWizardProps {
  mode: "create" | "update";
  /** Parsed current config object — only used when mode === "update" */
  initialConfig?: Record<string, unknown>;
  /** configId of the config being updated — used for display only */
  currentConfigName?: string;
  onClose: () => void;
}

// ─── AI Icon SVG ──────────────────────────────────────────────────────────────

function AiIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="2,20 9,7 13,13 16,9 22,20" />
      <polyline points="14.3,11 16,9 17.7,11.4" />
    </svg>
  );
}

// ─── Adapter / Target toggle button ──────────────────────────────────────────

function ToggleCard({
  label,
  desc,
  active,
  color,
  onClick,
}: {
  label: string;
  desc: string;
  active: boolean;
  color: "sky" | "emerald";
  onClick: () => void;
}) {
  const activeStyle =
    color === "sky"
      ? "border-sky-500 bg-sky-900/40 text-sky-200"
      : "border-emerald-500 bg-emerald-900/30 text-emerald-200";
  const checkStyle =
    color === "sky"
      ? "bg-sky-500 border-sky-500 text-white"
      : "bg-emerald-500 border-emerald-500 text-white";
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg border px-3 py-2.5 text-sm font-medium transition-colors text-left flex items-start gap-2 ${
        active ? activeStyle : "border-[#2a3044] bg-[#0f1117] text-slate-300 hover:border-sky-700"
      }`}
    >
      <span
        className={`mt-0.5 w-3.5 h-3.5 flex-shrink-0 rounded border text-[10px] flex items-center justify-center ${
          active ? checkStyle : "border-slate-600"
        }`}
      >
        {active ? "✓" : ""}
      </span>
      <span>
        {label}
        <span className="block text-[10px] text-slate-500 font-normal mt-0.5">{desc}</span>
      </span>
    </button>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

const EMPTY_WIZARD: WizardState = {
  name: "",
  description: "",
  protocol_adapters: ["OPCUA"],
  source_endpoints: "",
  sfc_targets: ["DEBUG-TARGET"],
  channels_description: "",
  additional_context: "",
};

export default function AiConfigWizard({
  mode,
  initialConfig,
  currentConfigName,
  onClose,
}: AiConfigWizardProps) {
  const navigate = useNavigate();
  const qc = useQueryClient();

  // Build initial wizard state depending on mode
  const initState: WizardState =
    mode === "update" && initialConfig && currentConfigName
      ? buildUpdateWizardState(initialConfig, currentConfigName)
      : { ...EMPTY_WIZARD };

  const [wizardStep, setWizardStep] = useState<WizardStep>(1);
  const [wizard, setWizard] = useState<WizardState>(initState);
  const [wizardError, setWizardError] = useState("");
  const [completedJob, setCompletedJob] = useState<GenerateConfigJobStatus | null>(null);

  // ── Helpers ────────────────────────────────────────────────────────────────
  function updateWizard(patch: Partial<WizardState>) {
    setWizard((prev) => ({ ...prev, ...patch }));
  }

  function toggleAdapter(id: string) {
    setWizard((prev) => ({
      ...prev,
      protocol_adapters: prev.protocol_adapters.includes(id)
        ? prev.protocol_adapters.filter((a) => a !== id)
        : [...prev.protocol_adapters, id],
    }));
  }

  function toggleTarget(id: string) {
    setWizard((prev) => ({
      ...prev,
      sfc_targets: prev.sfc_targets.includes(id)
        ? prev.sfc_targets.filter((t) => t !== id)
        : [...prev.sfc_targets, id],
    }));
  }

  // ── Generate mutation ──────────────────────────────────────────────────────
  const generateMut = useMutation({
    mutationFn: () => {
      // In update mode: embed the current config JSON in additional_context
      let ctx = wizard.additional_context ?? "";
      if (mode === "update" && initialConfig) {
        const cfgJson = JSON.stringify(initialConfig, null, 2);
        const prefix =
          "Current SFC configuration to update (keep compatible structure, improve or extend as requested):\n```json\n" +
          cfgJson +
          "\n```";
        ctx = ctx ? prefix + "\n\n" + ctx : prefix;
      }
      return generateConfig({
        name: wizard.name,
        description: wizard.description || undefined,
        protocol_adapters: wizard.protocol_adapters,
        source_endpoints: wizard.source_endpoints
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
        sfc_targets: wizard.sfc_targets,
        channels_description: wizard.channels_description,
        sampling_interval_ms: 1000,
        additional_context: ctx || undefined,
      });
    },
    onSuccess: (result: GenerateConfigJobStatus) => {
      qc.invalidateQueries({ queryKey: ["configs"] });
      setCompletedJob(result);
      setWizardStep(5); // advance to agent response step
    },
    onError: (err: unknown) => {
      const msg =
        err instanceof Error ? err.message : "Generation failed. Please try again.";
      setWizardError(msg);
    },
  });

  const isUpdate = mode === "update";

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="card w-full max-w-xl shadow-2xl flex flex-col gap-5 max-h-[90vh] overflow-y-auto">

        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-sky-300 flex items-center gap-2">
            <AiIcon className="w-5 h-5 shrink-0" />
            {isUpdate ? "Update Config using AI" : "AI-Guided Config Creation"}
          </h2>
          <button
            className="text-slate-500 hover:text-slate-300 text-lg leading-none"
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        {/* Context banner for update mode */}
        {isUpdate && wizardStep < 5 && (
          <div className="flex items-start gap-2 px-3 py-2 rounded-md bg-sky-950/40 border border-sky-800/40 text-xs text-sky-300">
            <AiIcon className="w-3.5 h-3.5 mt-0.5 shrink-0" />
            <span>
              Adapters &amp; targets were <span className="font-semibold">pre-selected</span> from
              your current config. Adjust as needed, then let the agent generate an updated version.
            </span>
          </div>
        )}

        {/* Progress bar — only steps 1–4 */}
        {wizardStep < 5 && (
          <div className="flex items-center gap-1">
            {([1, 2, 3, 4] as WizardStep[]).map((s) => (
              <div key={s} className="flex-1 flex flex-col items-center gap-1">
                <div
                  className={`h-1.5 w-full rounded-full transition-colors ${
                    wizardStep >= s ? "bg-sky-500" : "bg-[#2a3044]"
                  }`}
                />
                <span
                  className={`text-[10px] ${
                    wizardStep === s ? "text-sky-300 font-semibold" : "text-slate-500"
                  }`}
                >
                  {s === 1 ? "Basics" : s === 2 ? "Protocol" : s === 3 ? "Targets" : "Channels"}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* ── Step 1: Basics ── */}
        {wizardStep === 1 && (
          <div className="flex flex-col gap-3">
            <p className="text-xs text-slate-400">
              {isUpdate
                ? "Review the config name and description. The agent will generate a new version."
                : "Give your configuration a name so you can find it later."}
            </p>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-slate-400">
                Config name <span className="text-red-400">*</span>
              </span>
              <input
                className="bg-[#0f1117] border border-[#2a3044] rounded px-3 py-2 text-sm focus:border-sky-500 outline-none"
                placeholder="e.g. Line-A OPC-UA Config"
                value={wizard.name}
                onChange={(e) => updateWizard({ name: e.target.value })}
                autoFocus
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-slate-400">Description (optional)</span>
              <input
                className="bg-[#0f1117] border border-[#2a3044] rounded px-3 py-2 text-sm focus:border-sky-500 outline-none"
                placeholder="e.g. Assembly line A — temperature sensors"
                value={wizard.description}
                onChange={(e) => updateWizard({ description: e.target.value })}
              />
            </label>
          </div>
        )}

        {/* ── Step 2: Protocol Adapters ── */}
        {wizardStep === 2 && (
          <div className="flex flex-col gap-3">
            <p className="text-xs text-slate-400">
              Select one or more SFC protocol adapters (source side).{" "}
              {isUpdate && (
                <span className="text-sky-400 font-medium">
                  Pre-selected from your current config.
                </span>
              )}
            </p>
            <div className="grid grid-cols-2 gap-2">
              {SFC_ADAPTERS.map((a) => (
                <ToggleCard
                  key={a.id}
                  label={a.label}
                  desc={a.desc}
                  active={wizard.protocol_adapters.includes(a.id)}
                  color="sky"
                  onClick={() => toggleAdapter(a.id)}
                />
              ))}
            </div>
            <div className="flex flex-col gap-1 mt-1">
              <label className="text-xs text-slate-400">
                Source endpoint(s){" "}
                <span className="text-slate-600">(optional — one per line)</span>
              </label>
              <textarea
                className="bg-[#0f1117] border border-[#2a3044] rounded px-3 py-2 text-sm font-mono focus:border-sky-500 outline-none resize-none"
                rows={3}
                placeholder={"opc.tcp://192.168.1.10\n192.168.1.20\nhttps://api.example.com/data"}
                value={wizard.source_endpoints}
                onChange={(e) => updateWizard({ source_endpoints: e.target.value })}
              />
              <p className="text-[10px] text-slate-500">
                Enter host/IP addresses, OPC-UA endpoints, MQTT broker URLs, etc. The AI uses
                these as-is.
              </p>
            </div>
          </div>
        )}

        {/* ── Step 3: SFC Targets ── */}
        {wizardStep === 3 && (
          <div className="flex flex-col gap-4">
            {isUpdate && (
              <p className="text-xs text-sky-400 font-medium">
                Pre-selected from your current config. Add or remove targets as needed.
              </p>
            )}
            <div className="flex flex-col gap-2">
              <p className="text-xs text-slate-400 font-medium">AWS Service Targets</p>
              <div className="grid grid-cols-2 gap-2">
                {SFC_TARGETS_SERVICE.map((t) => (
                  <ToggleCard
                    key={t.id}
                    label={t.label}
                    desc={t.desc}
                    active={wizard.sfc_targets.includes(t.id)}
                    color="sky"
                    onClick={() => toggleTarget(t.id)}
                  />
                ))}
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <p className="text-xs text-slate-400 font-medium">Local / Edge Targets</p>
              <div className="grid grid-cols-2 gap-2">
                {SFC_TARGETS_LOCAL.map((t) => (
                  <ToggleCard
                    key={t.id}
                    label={t.label}
                    desc={t.desc}
                    active={wizard.sfc_targets.includes(t.id)}
                    color="emerald"
                    onClick={() => toggleTarget(t.id)}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── Step 4: Channels + context ── */}
        {wizardStep === 4 && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-slate-400">
                {isUpdate
                  ? "Describe what you want to change or add"
                  : "Describe the data channels to collect"}
              </label>
              <textarea
                className="bg-[#0f1117] border border-[#2a3044] rounded px-3 py-2 text-sm focus:border-sky-500 outline-none resize-y"
                rows={4}
                placeholder={
                  isUpdate
                    ? `e.g. "Add a sinus channel, change sampling to 500ms, add AWS IoT Core as additional target"`
                    : `e.g. "Collect temperature from ns=2;i=1001 and pressure from ns=2;i=1002 every 500 ms."`
                }
                value={wizard.channels_description}
                onChange={(e) => updateWizard({ channels_description: e.target.value })}
              />
              <p className="text-[10px] text-slate-500">
                {isUpdate
                  ? "Describe changes or new requirements. The agent will update the existing config structure accordingly."
                  : "Mention tag names, node IDs, register addresses, data types or units."}
              </p>
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-xs text-slate-400">
                Additional context / requirements{" "}
                <span className="text-slate-600">(optional)</span>
              </label>
              <textarea
                className="bg-[#0f1117] border border-[#2a3044] rounded px-3 py-2 text-sm focus:border-sky-500 outline-none resize-y"
                rows={3}
                placeholder="Any extra details — e.g. security mode, certificate paths, retry behaviour, custom adapter settings…"
                value={wizard.additional_context}
                onChange={(e) => updateWizard({ additional_context: e.target.value })}
              />
            </div>

            {isUpdate && (
              <div className="flex items-start gap-2 px-3 py-2 rounded bg-[#0f1117] border border-[#2a3044] text-xs text-slate-400">
                <svg viewBox="0 0 24 24" className="w-3.5 h-3.5 mt-0.5 shrink-0 text-sky-400" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <span>
                  The <span className="text-sky-300 font-medium">current config JSON</span> will be
                  automatically included so the agent can produce a compatible update.
                </span>
              </div>
            )}

            {wizardError && (
              <p className="text-xs text-red-400 bg-red-950/30 border border-red-800/40 rounded px-3 py-2">
                {wizardError}
              </p>
            )}

            {generateMut.isPending && (
              <div className="flex flex-col gap-1 text-xs bg-sky-950/30 border border-sky-800/30 rounded px-3 py-2">
                <div className="flex items-center gap-2 text-sky-400">
                  <span className="spinner" />
                  <span className="font-medium">
                    SFC Agent is {isUpdate ? "updating" : "generating"} your config…
                  </span>
                </div>
                <p className="text-slate-500 pl-5">
                  The agent reasons through SFC schema, adapter classes and target writers. This
                  typically takes <span className="text-sky-500">1–5 minutes</span> — please keep
                  this window open.
                </p>
              </div>
            )}
          </div>
        )}

        {/* ── Step 5: Agent Response ── */}
        {wizardStep === 5 && (
          <div className="flex flex-col gap-4">
            {/* Header bar */}
            <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-sky-950/30 border border-sky-800/30">
              <AiIcon className="w-4 h-4 text-sky-400 shrink-0" />
              <span className="text-xs text-sky-300 font-semibold uppercase tracking-wider">
                Agent Response
              </span>
              {completedJob?.configId && (
                <span className="ml-auto text-xs text-slate-500 font-mono truncate max-w-[180px]">
                  {completedJob.name ?? completedJob.configId}
                </span>
              )}
            </div>

            {/* Still pending — show spinner */}
            {generateMut.isPending && !completedJob && (
              <div className="flex flex-col gap-1 text-xs">
                <div className="flex items-center gap-2 text-sky-400">
                  <span className="spinner" />
                  <span className="font-medium">
                    SFC Agent is {isUpdate ? "updating" : "generating"} your config…
                  </span>
                </div>
                <p className="text-slate-500 pl-5">
                  This typically takes <span className="text-sky-500">1–5 minutes</span>.
                </p>
              </div>
            )}

            {/* Completed — render agent markdown response or success summary */}
            {completedJob && completedJob.status === "COMPLETE" && (
              <div className="flex flex-col gap-3">
                <div className="rounded-md border border-[#2a3044] bg-[#0d1117] overflow-auto max-h-72">
                  <MarkdownRenderer
                    content={
                      `✅ **Config ${isUpdate ? "updated" : "generated"} successfully!**\n\n` +
                      `A new config version was saved${completedJob.name ? ` as **${completedJob.name}**` : ""}.\n\n` +
                      `> The agent applied your requested changes and produced a valid SFC configuration. ` +
                      `Click **"Open Generated Config"** to review and save as a new version.`
                    }
                  />
                </div>
                <button
                  className="btn btn-primary flex items-center gap-2 self-end"
                  onClick={() => {
                    onClose();
                    if (completedJob.configId) {
                      navigate(`/configs/${completedJob.configId}`);
                    }
                  }}
                >
                  <AiIcon className="w-4 h-4 shrink-0" />
                  Open Generated Config →
                </button>
              </div>
            )}

            {/* Failed */}
            {completedJob && completedJob.status === "FAILED" && (
              <div className="flex flex-col gap-2">
                <p className="text-xs text-red-400 bg-red-950/30 border border-red-800/40 rounded px-3 py-2">
                  {completedJob.error ?? "Generation failed. Please try again."}
                </p>
                <button
                  className="btn btn-secondary self-start"
                  onClick={() => { setWizardStep(4); setWizardError(""); setCompletedJob(null); }}
                >
                  ← Back to step 4
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── Navigation buttons (steps 1–4 only) ── */}
        {wizardStep < 5 && (
          <div className="flex justify-between items-center pt-1 border-t border-[#2a3044]">
            <button
              className="btn btn-secondary"
              onClick={() => {
                if (wizardStep === 1) {
                  onClose();
                } else {
                  setWizardStep((s) => (s - 1) as WizardStep);
                  setWizardError("");
                }
              }}
            >
              {wizardStep === 1 ? "Cancel" : "← Back"}
            </button>

            {wizardStep < 4 ? (
              <button
                className="btn btn-primary"
                disabled={wizardStep === 1 && !wizard.name.trim()}
                onClick={() => setWizardStep((s) => (s + 1) as WizardStep)}
              >
                Next →
              </button>
            ) : (
              <button
                className="btn btn-primary"
                disabled={generateMut.isPending}
                onClick={() => {
                  setWizardError("");
                  generateMut.mutate();
                }}
              >
                {generateMut.isPending ? (
                  <span className="spinner" />
                ) : (
                  <span className="flex items-center gap-1.5">
                    <AiIcon className="w-4 h-4 shrink-0" />
                    {isUpdate ? "Generate Update" : "Generate Config"}
                  </span>
                )}
              </button>
            )}
          </div>
        )}

        {/* ── Close button on step 5 (if not navigating away) ── */}
        {wizardStep === 5 && !generateMut.isPending && (
          <div className="flex justify-end pt-1 border-t border-[#2a3044]">
            <button className="btn btn-secondary" onClick={onClose}>
              Close
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
