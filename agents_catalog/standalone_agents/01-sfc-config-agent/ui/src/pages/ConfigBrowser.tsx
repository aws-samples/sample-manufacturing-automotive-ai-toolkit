import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  listConfigs,
  listPackages,
  listConfigVersions,
  createConfig,
  getFocus,
  deleteConfig,
  generateConfig,
  type GenerateConfigJobStatus,
  type LaunchPackage,
} from "../api/client";
import StatusBadge from "../components/StatusBadge";
import ConfirmDialog from "../components/ConfirmDialog";
import RefreshButton from "../components/RefreshButton";
import SortableHeader from "../components/SortableHeader";
import TagFilter from "../components/TagFilter";
import { useSortable } from "../hooks/useSortable";
import { useState, useMemo, useRef, useEffect } from "react";

// ─── DeployedVersionBadge ─────────────────────────────────────────────────────
// Shows "vN deployed" where N is the version label of the currently deployed version.

function DeployedVersionBadge({
  configId,
  deployedPackages,
  onClick,
}: {
  configId: string;
  deployedPackages: LaunchPackage[];
  onClick: () => void;
}) {
  const { data: versions } = useQuery({
    queryKey: ["configVersions", configId],
    queryFn: () => listConfigVersions(configId),
    staleTime: 60_000,
  });

  // Build vN label for the deployed version (oldest version = v1)
  const vLabel = (() => {
    if (!versions || deployedPackages.length === 0) return null;
    // Take the first package's configVersion (most common: one LP per config)
    const deployedVersion = deployedPackages[0].configVersion;
    const ordered = [...versions].reverse(); // oldest first → v1
    const idx = ordered.findIndex((v) => v.version === deployedVersion);
    return idx >= 0 ? `v${idx + 1}` : null;
  })();

  const pkgCount = deployedPackages.length;
  const title = pkgCount === 1
    ? `Go to package ${deployedPackages[0].packageId}`
    : `Show ${pkgCount} packages for this config`;

  return (
    <button
      type="button"
      className="cursor-pointer hover:opacity-80 transition-opacity"
      onClick={onClick}
      title={title}
    >
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-teal-900/40 text-teal-300 border border-teal-700/50">
        {vLabel ? (
          <><span className="text-teal-200 font-bold">{vLabel}</span> deployed</>
        ) : (
          "deployed"
        )}
      </span>
    </button>
  );
}

// ─── Types ───────────────────────────────────────────────────────────────────

type ConfigRow = {
  configId: string;
  version: string;
  name: string;
  description?: string;
  status: string;
  createdAt: string;
  tags?: string[];
};

function getValue(item: ConfigRow, column: string): string | number | undefined {
  switch (column) {
    case "name":    return item.name?.toLowerCase();
    case "version": return item.version;
    case "status":  return item.status;
    case "created": return item.createdAt;
    default:        return undefined;
  }
}

// ─── SFC Protocol Adapters (source side) ─────────────────────────────────────

const SFC_ADAPTERS = [
  { id: "OPCUA",      label: "OPC-UA",            desc: "OPC Unified Architecture"           },
  { id: "Modbus",     label: "Modbus TCP",         desc: "Modbus TCP/IP industrial standard"  },
  { id: "MQTT",       label: "MQTT",               desc: "Pub/sub IoT messaging"              },
  { id: "S7",         label: "S7 / Siemens",       desc: "S7-300/400/1200/1500 native"        },
  { id: "OPCDA",      label: "OPC-DA",             desc: "Legacy Windows OPC Data Access"     },
  { id: "PCCC",       label: "PCCC / Allen-Bradley",desc: "Rockwell / Allen-Bradley PLCs"     },
  { id: "SLMP",       label: "SLMP / Melsec",      desc: "Mitsubishi Seamless Message Proto." },
  { id: "ADS",        label: "ADS / Beckhoff",     desc: "TwinCAT / Beckhoff PLCs"            },
  { id: "J1939",      label: "J1939",              desc: "Heavy-duty vehicle CAN bus"         },
  { id: "SNMP",       label: "SNMP",               desc: "Network device management"          },
  { id: "REST",       label: "REST",               desc: "HTTP GET from RESTful endpoints"    },
  { id: "SQL",        label: "SQL",                desc: "JDBC relational database queries"   },
  { id: "NATS",       label: "NATS",               desc: "Cloud-native NATS messaging"        },
  { id: "Simulator",  label: "Simulator",          desc: "Synthetic data for testing"         },
];

// ─── SFC Targets (destination side) ──────────────────────────────────────────

const SFC_TARGETS_SERVICE = [
  { id: "AWS IoT Core",         label: "AWS IoT Core",        desc: "Managed IoT device connectivity"    },
  { id: "AWS SiteWise",         label: "AWS SiteWise",        desc: "Industrial equipment data at scale" },
  { id: "AWS S3",               label: "AWS S3",              desc: "Object storage"                     },
  { id: "AWS S3-Tables",        label: "S3 Tables (Iceberg)", desc: "Iceberg tables on S3"               },
  { id: "AWS MSK",              label: "AWS MSK (Kafka)",     desc: "Managed Kafka"                      },
  { id: "AWS Kinesis Firehose", label: "Kinesis Firehose",    desc: "Streaming delivery"                 },
  { id: "AWS Lambda",           label: "AWS Lambda",          desc: "Event-driven serverless compute"    },
  { id: "AWS SNS",              label: "AWS SNS",             desc: "Pub/sub notifications"              },
  { id: "AWS SQS",              label: "AWS SQS",             desc: "Managed message queue"              },
];

const SFC_TARGETS_LOCAL = [
  { id: "Debug",             label: "Debug",             desc: "Console output for local testing"    },
  { id: "MQTT",              label: "MQTT (local)",      desc: "MQTT broker target"                  },
  { id: "NATS",              label: "NATS (local)",      desc: "NATS messaging target"               },
  { id: "File",              label: "File",              desc: "Write to local filesystem"           },
  { id: "OPCUA Server",      label: "OPC-UA Server",     desc: "Expose data via OPC-UA server"       },
  { id: "OPCUA Writer",      label: "OPC-UA Writer",     desc: "Write to external OPC-UA nodes"      },
  { id: "AWS SiteWise Edge", label: "SiteWise Edge",     desc: "Local SiteWise edge processing"      },
];

// ─── Wizard state ─────────────────────────────────────────────────────────────

type WizardStep = 1 | 2 | 3 | 4;

interface WizardState {
  name: string;
  description: string;
  protocol_adapters: string[];
  source_endpoints: string;   // free-text, one endpoint per line
  sfc_targets: string[];
  channels_description: string;
  additional_context: string;
}

const EMPTY_WIZARD: WizardState = {
  name: "",
  description: "",
  protocol_adapters: ["OPCUA"],
  source_endpoints: "",
  sfc_targets: ["Debug"],
  channels_description: "",
  additional_context: "",
};

// ─── Component ───────────────────────────────────────────────────────────────

export default function ConfigBrowser() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: rawConfigs, isLoading, refetch: refetchConfigs, isFetching: isFetchingConfigs } = useQuery({
    queryKey: ["configs"],
    queryFn: listConfigs,
  });
  const configs: ConfigRow[] = Array.isArray(rawConfigs) ? rawConfigs : [];

  const { data: rawPackages } = useQuery({ queryKey: ["packages"], queryFn: listPackages });
  const usedConfigIds = new Set(
    (Array.isArray(rawPackages) ? rawPackages : []).map((p) => p.configId)
  );

  const { data: focus } = useQuery({ queryKey: ["focus"], queryFn: getFocus, staleTime: 30_000 });
  const focusedConfigId = focus?.focusedConfigId;

  // ── Manual new-config modal ──────────────────────────────────────────────
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");

  // ── Delete confirmation ──────────────────────────────────────────────────
  const [deleteTarget, setDeleteTarget] = useState<{ configId: string; name: string } | null>(null);

  // ── Creation choice popover ──────────────────────────────────────────────
  const [showChoice, setShowChoice] = useState(false);
  const choiceRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!showChoice) return;
    const handler = (e: MouseEvent) => {
      if (choiceRef.current && !choiceRef.current.contains(e.target as Node)) {
        setShowChoice(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showChoice]);

  // ── AI Wizard state ──────────────────────────────────────────────────────
  const [showWizard, setShowWizard] = useState(false);
  const [wizardStep, setWizardStep] = useState<WizardStep>(1);
  const [wizard, setWizard] = useState<WizardState>(EMPTY_WIZARD);
  const [wizardError, setWizardError] = useState("");

  function openWizard() {
    setShowChoice(false);
    setWizard(EMPTY_WIZARD);
    setWizardStep(1);
    setWizardError("");
    setShowWizard(true);
  }

  function openManual() {
    setShowChoice(false);
    setNewName("");
    setNewDesc("");
    setShowNew(true);
  }

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

  function toggleSfcTarget(id: string) {
    setWizard((prev) => ({
      ...prev,
      sfc_targets: prev.sfc_targets.includes(id)
        ? prev.sfc_targets.filter((t) => t !== id)
        : [...prev.sfc_targets, id],
    }));
  }

  // ── Mutations ────────────────────────────────────────────────────────────
  const createMut = useMutation({
    mutationFn: () => createConfig({ name: newName, description: newDesc, content: "{}" }),
    onSuccess: (cfg) => {
      qc.invalidateQueries({ queryKey: ["configs"] });
      setShowNew(false);
      navigate(`/configs/${cfg.configId}`);
    },
  });

  const generateMut = useMutation({
    mutationFn: () =>
      generateConfig({
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
        additional_context: wizard.additional_context || undefined,
      }),
    onSuccess: (result: GenerateConfigJobStatus) => {
      qc.invalidateQueries({ queryKey: ["configs"] });
      setShowWizard(false);
      if (result.configId) {
        navigate(`/configs/${result.configId}`);
      } else {
        navigate("/configs");
      }
    },
    onError: (err: unknown) => {
      const msg =
        err instanceof Error ? err.message : "Generation failed. Please try again.";
      setWizardError(msg);
    },
  });

  const deleteMut = useMutation({
    mutationFn: (configId: string) => deleteConfig(configId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["configs"] });
      setDeleteTarget(null);
    },
  });

  // ── Sorting / filtering ──────────────────────────────────────────────────
  function deriveConfigStatus(configId: string): string {
    if (configId === focusedConfigId) return "focused";
    if (usedConfigIds.has(configId)) return "deployed";
    return "unused";
  }

  const { sort, toggle, sorted } = useSortable(configs, "created", "desc", getValue);

  const [activeTags, setActiveTags] = useState<string[]>([]);
  const allTags = useMemo(() => {
    const s = new Set<string>();
    configs.forEach((c) => (c.tags ?? []).forEach((t) => s.add(t)));
    return Array.from(s).sort();
  }, [configs]);

  const tagFiltered = useMemo(() => {
    if (activeTags.length === 0) return sorted;
    return sorted.filter((c) => activeTags.every((t) => (c.tags ?? []).includes(t)));
  }, [sorted, activeTags]);

  function toggleTag(tag: string) {
    setActiveTags((prev) => prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]);
  }

  // ─── Render ──────────────────────────────────────────────────────────────
  return (
    <div className="p-8 max-w-[1440px] mx-auto">
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-lg font-semibold">SFC Configurations</h1>
        <div className="flex items-center gap-2">
          <RefreshButton onClick={() => refetchConfigs()} loading={isFetchingConfigs} title="Refresh configs" />

          {/* ── New Config button with choice popover ── */}
          <div className="relative" ref={choiceRef}>
            <button className="btn btn-primary" onClick={() => setShowChoice((v) => !v)}>
              + New Config
            </button>
            {showChoice && (
              <div className="absolute right-0 top-full mt-1 z-50 bg-[#1a2030] border border-[#2a3044] rounded-lg shadow-xl w-52 overflow-hidden">
                <button
                  className="w-full text-left px-4 py-3 text-sm hover:bg-[#232d42] transition-colors text-slate-200"
                  onClick={openManual}
                >
                  <span className="font-medium">Create manually</span>
                  <p className="text-xs text-slate-500 mt-0.5">Start with a blank JSON editor</p>
                </button>
                <div className="border-t border-[#2a3044]" />
                <button
                  className="w-full text-left px-4 py-3 text-sm hover:bg-[#232d42] transition-colors text-slate-200"
                  onClick={openWizard}
                >
                  <span className="font-medium text-sky-400 flex items-center gap-1.5">
                    <svg viewBox="0 0 24 24" className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="2,20 9,7 13,13 16,9 22,20" />
                      <polyline points="14.3,11 16,9 17.7,11.4" />
                    </svg>
                    AI-guided Config
                  </span>
                  <p className="text-xs text-slate-500 mt-0.5">Wizard → agent generates config</p>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {isLoading && <p className="text-slate-500 text-sm">Loading…</p>}

      {configs.length === 0 && !isLoading && (
        <p className="text-slate-500 text-sm italic">No configurations yet. Create one to get started.</p>
      )}

      {sorted.length > 0 && allTags.length > 0 && (
        <div className="mb-3">
          <TagFilter allTags={allTags} activeTags={activeTags} onToggle={toggleTag} onClear={() => setActiveTags([])} total={sorted.length} filtered={tagFiltered.length} />
        </div>
      )}

      {sorted.length > 0 && (
        <div className="card overflow-hidden p-0">
          <table className="table-base">
            <thead>
              <tr>
                <SortableHeader column="name"    label="Name"    sort={sort} onToggle={toggle} />
                <th>Config ID</th>
                <SortableHeader column="version" label="Version" sort={sort} onToggle={toggle} />
                <SortableHeader column="status"  label="Status"  sort={sort} onToggle={toggle} />
                <SortableHeader column="created" label="Created" sort={sort} onToggle={toggle} />
                <th></th>
              </tr>
            </thead>
            <tbody>
              {tagFiltered.map((c) => {
                const isFocused = c.configId === focusedConfigId;
                return (
                  <tr
                    key={c.configId}
                    className={`cursor-pointer ${isFocused ? "bg-sky-950/40 hover:bg-sky-950/60" : ""}`}
                    onClick={() => navigate(`/configs/${c.configId}`)}
                  >
                    <td>
                      <div className="font-medium flex items-center gap-2 flex-wrap">
                        {c.name}
                        {isFocused && (
                          <span className="text-[10px] font-mono font-semibold bg-sky-900/60 text-sky-300 border border-sky-700 rounded px-1.5 py-0.5 leading-none">FOCUS</span>
                        )}
                      </div>
                      {c.tags && c.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {c.tags.map((tag) => (
                            <span key={tag} className="inline-flex px-1.5 py-0.5 rounded bg-sky-900/30 text-sky-400 text-[10px] font-medium ring-1 ring-sky-800/40">{tag}</span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="font-mono text-xs text-slate-400">{c.configId}</td>
                    <td className="font-mono text-xs text-slate-400 max-w-[200px] truncate">{c.version}</td>
                    <td onClick={(e) => e.stopPropagation()}>
                      {(() => {
                        const derived = deriveConfigStatus(c.configId);
                        if (derived === "deployed") {
                          const pkgs = (Array.isArray(rawPackages) ? rawPackages : []).filter((p) => p.configId === c.configId);
                          const dest = pkgs.length === 1 ? `/packages/${pkgs[0].packageId}` : `/packages?configId=${c.configId}`;
                          return (
                            <DeployedVersionBadge
                              configId={c.configId}
                              deployedPackages={pkgs}
                              onClick={() => navigate(dest)}
                            />
                          );
                        }
                        return <StatusBadge status={derived} />;
                      })()}
                    </td>
                    <td className="text-xs text-slate-500">{new Date(c.createdAt).toLocaleDateString()}</td>
                    <td className="flex items-center gap-1">
                      <button className="btn btn-ghost text-xs" onClick={(e) => { e.stopPropagation(); navigate(`/configs/${c.configId}`); }}>Edit</button>
                      {!isFocused && (
                        usedConfigIds.has(c.configId) ? (
                          <span title="Used by one or more launch packages — cannot be deleted." className="btn btn-ghost text-xs text-slate-600 cursor-not-allowed opacity-50" onClick={(e) => e.stopPropagation()}>Delete</span>
                        ) : (
                          <button className="btn btn-ghost text-xs text-red-400 hover:text-red-300" onClick={(e) => { e.stopPropagation(); setDeleteTarget({ configId: c.configId, name: c.name }); }}>Delete</button>
                        )
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Delete confirmation ── */}
      {deleteTarget && (
        <ConfirmDialog
          title="Delete Configuration"
          message={`Are you sure you want to delete "${deleteTarget.name}"? All versions will be marked as deleted.`}
          confirmLabel={deleteMut.isPending ? "Deleting…" : "Delete"}
          danger
          onConfirm={() => deleteMut.mutate(deleteTarget.configId)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}

      {/* ── Manual new-config modal (unchanged behaviour) ── */}
      {showNew && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="card w-full max-w-md shadow-xl space-y-4">
            <h2 className="text-base font-semibold">New Configuration</h2>
            <input
              className="w-full bg-[#0f1117] border border-[#2a3044] rounded px-3 py-2 text-sm"
              placeholder="Config name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <input
              className="w-full bg-[#0f1117] border border-[#2a3044] rounded px-3 py-2 text-sm"
              placeholder="Description (optional)"
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
            />
            <div className="flex justify-end gap-2">
              <button className="btn btn-secondary" onClick={() => setShowNew(false)}>Cancel</button>
              <button className="btn btn-primary" disabled={!newName || createMut.isPending} onClick={() => createMut.mutate()}>
                {createMut.isPending ? <span className="spinner" /> : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── AI Wizard modal ── */}
      {showWizard && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="card w-full max-w-xl shadow-2xl flex flex-col gap-5 max-h-[90vh] overflow-y-auto">

            {/* Header */}
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-sky-300 flex items-center gap-2">
                <svg viewBox="0 0 24 24" className="w-5 h-5 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="2,20 9,7 13,13 16,9 22,20" />
                  <polyline points="14.3,11 16,9 17.7,11.4" />
                </svg>
                AI-Guided Config Creation
              </h2>
              <button className="text-slate-500 hover:text-slate-300 text-lg leading-none" onClick={() => setShowWizard(false)}>✕</button>
            </div>

            {/* Progress bar */}
            <div className="flex items-center gap-1">
              {([1, 2, 3, 4] as WizardStep[]).map((s) => (
                <div key={s} className="flex-1 flex flex-col items-center gap-1">
                  <div className={`h-1.5 w-full rounded-full transition-colors ${wizardStep >= s ? "bg-sky-500" : "bg-[#2a3044]"}`} />
                  <span className={`text-[10px] ${wizardStep === s ? "text-sky-300 font-semibold" : "text-slate-500"}`}>
                    {s === 1 ? "Basics" : s === 2 ? "Protocol" : s === 3 ? "Targets" : "Channels"}
                  </span>
                </div>
              ))}
            </div>

            {/* ── Step 1: Basics ── */}
            {wizardStep === 1 && (
              <div className="flex flex-col gap-3">
                <p className="text-xs text-slate-400">Give your configuration a name so you can find it later.</p>
                <label className="flex flex-col gap-1">
                  <span className="text-xs text-slate-400">Config name <span className="text-red-400">*</span></span>
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

            {/* ── Step 2: Protocol Adapters (multi-select) ── */}
            {wizardStep === 2 && (
              <div className="flex flex-col gap-3">
                <p className="text-xs text-slate-400">
                  Select one or more SFC protocol adapters (source side). <span className="text-slate-500">Multi-select is allowed.</span>
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {SFC_ADAPTERS.map((a) => {
                    const active = wizard.protocol_adapters.includes(a.id);
                    return (
                      <button
                        key={a.id}
                        type="button"
                        onClick={() => toggleAdapter(a.id)}
                        className={`rounded-lg border px-3 py-2.5 text-sm font-medium transition-colors text-left flex items-start gap-2 ${
                          active
                            ? "border-sky-500 bg-sky-900/40 text-sky-200"
                            : "border-[#2a3044] bg-[#0f1117] text-slate-300 hover:border-sky-700"
                        }`}
                      >
                        <span className={`mt-0.5 w-3.5 h-3.5 flex-shrink-0 rounded border text-[10px] flex items-center justify-center ${active ? "bg-sky-500 border-sky-500 text-white" : "border-slate-600"}`}>
                          {active ? "✓" : ""}
                        </span>
                        <span>
                          {a.label}
                          <span className="block text-[10px] text-slate-500 font-normal mt-0.5">{a.desc}</span>
                        </span>
                      </button>
                    );
                  })}
                </div>

                <div className="flex flex-col gap-1 mt-1">
                  <label className="text-xs text-slate-400">
                    Source endpoint(s) <span className="text-slate-600">(optional — one per line)</span>
                  </label>
                  <textarea
                    className="bg-[#0f1117] border border-[#2a3044] rounded px-3 py-2 text-sm font-mono focus:border-sky-500 outline-none resize-none"
                    rows={3}
                    placeholder={"opc.tcp://192.168.1.10\n192.168.1.20\nhttps://api.example.com/data"}
                    value={wizard.source_endpoints}
                    onChange={(e) => updateWizard({ source_endpoints: e.target.value })}
                  />
                  <p className="text-[10px] text-slate-500">Enter host/IP addresses, OPC-UA endpoints, MQTT broker URLs, etc. The AI uses these as-is.</p>
                </div>
              </div>
            )}

            {/* ── Step 3: SFC Targets (multi-select) ── */}
            {wizardStep === 3 && (
              <div className="flex flex-col gap-4">
                <div className="flex flex-col gap-2">
                  <p className="text-xs text-slate-400 font-medium">AWS Service Targets</p>
                  <div className="grid grid-cols-2 gap-2">
                    {SFC_TARGETS_SERVICE.map((t) => {
                      const active = wizard.sfc_targets.includes(t.id);
                      return (
                        <button
                          key={t.id}
                          type="button"
                          onClick={() => toggleSfcTarget(t.id)}
                          className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors text-left flex items-start gap-2 ${
                            active
                              ? "border-sky-500 bg-sky-900/40 text-sky-200"
                              : "border-[#2a3044] bg-[#0f1117] text-slate-300 hover:border-sky-700"
                          }`}
                        >
                          <span className={`mt-0.5 w-3.5 h-3.5 flex-shrink-0 rounded border text-[10px] flex items-center justify-center ${active ? "bg-sky-500 border-sky-500 text-white" : "border-slate-600"}`}>
                            {active ? "✓" : ""}
                          </span>
                          <span>
                            {t.label}
                            <span className="block text-[10px] text-slate-500 font-normal mt-0.5">{t.desc}</span>
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div className="flex flex-col gap-2">
                  <p className="text-xs text-slate-400 font-medium">Local / Edge Targets</p>
                  <div className="grid grid-cols-2 gap-2">
                    {SFC_TARGETS_LOCAL.map((t) => {
                      const active = wizard.sfc_targets.includes(t.id);
                      return (
                        <button
                          key={t.id}
                          type="button"
                          onClick={() => toggleSfcTarget(t.id)}
                          className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors text-left flex items-start gap-2 ${
                            active
                              ? "border-emerald-500 bg-emerald-900/30 text-emerald-200"
                              : "border-[#2a3044] bg-[#0f1117] text-slate-300 hover:border-emerald-700"
                          }`}
                        >
                          <span className={`mt-0.5 w-3.5 h-3.5 flex-shrink-0 rounded border text-[10px] flex items-center justify-center ${active ? "bg-emerald-500 border-emerald-500 text-white" : "border-slate-600"}`}>
                            {active ? "✓" : ""}
                          </span>
                          <span>
                            {t.label}
                            <span className="block text-[10px] text-slate-500 font-normal mt-0.5">{t.desc}</span>
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {/* ── Step 4: Channels + additional context ── */}
            {wizardStep === 4 && (
              <div className="flex flex-col gap-3">
                <div className="flex flex-col gap-1">
                  <label className="text-xs text-slate-400">Describe the data channels to collect</label>
                  <textarea
                    className="bg-[#0f1117] border border-[#2a3044] rounded px-3 py-2 text-sm focus:border-sky-500 outline-none resize-y"
                    rows={4}
                    placeholder={`e.g. "Collect temperature from ns=2;i=1001 and pressure from ns=2;i=1002 every 500 ms. Also include machine status from the Status node."`}
                    value={wizard.channels_description}
                    onChange={(e) => updateWizard({ channels_description: e.target.value })}
                  />
                  <p className="text-[10px] text-slate-500">Mention tag names, node IDs, register addresses, data types or units. The AI infers sensible defaults for anything omitted.</p>
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-xs text-slate-400">Additional context / requirements <span className="text-slate-600">(optional)</span></label>
                  <textarea
                    className="bg-[#0f1117] border border-[#2a3044] rounded px-3 py-2 text-sm focus:border-sky-500 outline-none resize-y"
                    rows={3}
                    placeholder={`Any extra details — e.g. security mode, certificate paths, retry behaviour, custom adapter settings, environment constraints…`}
                    value={wizard.additional_context}
                    onChange={(e) => updateWizard({ additional_context: e.target.value })}
                  />
                </div>

                {wizardError && (
                  <p className="text-xs text-red-400 bg-red-950/30 border border-red-800/40 rounded px-3 py-2">{wizardError}</p>
                )}

                {generateMut.isPending && (
                  <div className="flex flex-col gap-1 text-xs bg-sky-950/30 border border-sky-800/30 rounded px-3 py-2">
                    <div className="flex items-center gap-2 text-sky-400">
                      <span className="spinner" />
                      <span className="font-medium">SFC Agent is generating your config…</span>
                    </div>
                    <p className="text-slate-500 pl-5">
                      The agent reasons through SFC schema, adapter classes and target writers.
                      This typically takes <span className="text-sky-500">1–5 minutes</span> — please keep this window open.
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* ── Navigation buttons ── */}
            <div className="flex justify-between items-center pt-1 border-t border-[#2a3044]">
              <button
                className="btn btn-secondary"
                onClick={() => {
                  if (wizardStep === 1) { setShowWizard(false); }
                  else { setWizardStep((s) => (s - 1) as WizardStep); setWizardError(""); }
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
                  onClick={() => { setWizardError(""); generateMut.mutate(); }}
                >
                  {generateMut.isPending ? <span className="spinner" /> : (
                    <span className="flex items-center gap-1.5">
                      <svg viewBox="0 0 24 24" className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="2,20 9,7 13,13 16,9 22,20" />
                        <polyline points="14.3,11 16,9 17.7,11.4" />
                      </svg>
                      Generate Config
                    </span>
                  )}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
