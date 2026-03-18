import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  listConfigs,
  listPackages,
  listConfigVersions,
  createConfig,
  getFocus,
  deleteConfig,
  type LaunchPackage,
} from "../api/client";
import StatusBadge from "../components/StatusBadge";
import ConfirmDialog from "../components/ConfirmDialog";
import RefreshButton from "../components/RefreshButton";
import SortableHeader from "../components/SortableHeader";
import TagFilter from "../components/TagFilter";
import AiConfigWizard from "../components/AiConfigWizard";
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

  function openWizard() {
    setShowChoice(false);
    setShowWizard(true);
  }

  function openManual() {
    setShowChoice(false);
    setNewName("");
    setNewDesc("");
    setShowNew(true);
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

      {/* ── AI Wizard modal (shared component, create mode) ── */}
      {showWizard && (
        <AiConfigWizard
          mode="create"
          onClose={() => setShowWizard(false)}
        />
      )}
    </div>
  );
}
