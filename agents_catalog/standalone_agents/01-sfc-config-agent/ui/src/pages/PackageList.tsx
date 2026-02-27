import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useState, useEffect } from "react";
import { listPackages, deepDeletePackage, createGgComponent, listConfigs } from "../api/client";
import type { LaunchPackage } from "../api/client";
import StatusBadge from "../components/StatusBadge";
import HeartbeatStatusLed from "../components/HeartbeatStatusLed";
import ConfirmDialog from "../components/ConfirmDialog";
import RefreshButton from "../components/RefreshButton";
import SortableHeader from "../components/SortableHeader";
import TagFilter from "../components/TagFilter";
import { useSortable } from "../hooks/useSortable";
import { useMemo } from "react";

function getValue(item: LaunchPackage & { _configName?: string }, column: string): string | number | undefined {
  switch (column) {
    case "packageId":   return item.packageId;
    case "config":      return (item._configName ?? item.configId).toLowerCase();
    case "status":      return item.status;
    case "lastSeen":    return item.lastHeartbeatAt ?? "";
    case "created":     return item.createdAt;
    default:            return undefined;
  }
}

export default function PackageList() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [dangerOpen, setDangerOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [searchParams] = useSearchParams();
  const [configFilter, setConfigFilter] = useState<string | null>(
    searchParams.get("configId")
  );

  // Sync if URL param changes (e.g. back navigation)
  useEffect(() => {
    setConfigFilter(searchParams.get("configId"));
  }, [searchParams]);

  const {
    data: rawPackages,
    isLoading,
    refetch: refetchPackages,
    isFetching: isFetchingPackages,
  } = useQuery({
    queryKey: ["packages"],
    queryFn: listPackages,
    refetchInterval: 15_000,
  });

  const { data: configs, refetch: refetchConfigs, isFetching: isFetchingConfigs } = useQuery({
    queryKey: ["configs"],
    queryFn: listConfigs,
  });

  const configNameMap: Record<string, string> = Object.fromEntries(
    (configs ?? []).map((c) => [c.configId, c.name])
  );

  // Augment packages with resolved config name for sorting
  type AugPkg = LaunchPackage & { _configName?: string };
  const packages: AugPkg[] = (rawPackages ?? []).map((p) => ({
    ...p,
    _configName: configNameMap[p.configId],
  }));

  const { sort, toggle, sorted } = useSortable(packages, "created", "desc", getValue);

  // ── Tag filter ────────────────────────────────────────────────────────────
  const [activeTags, setActiveTags] = useState<string[]>([]);
  const allTags = useMemo(() => {
    const s = new Set<string>();
    packages.forEach((p) => ((p as { tags?: string[] }).tags ?? []).forEach((t) => s.add(t)));
    return Array.from(s).sort();
  }, [packages]);

  const tagFiltered = useMemo(() => {
    let result = sorted;
    if (configFilter) {
      result = result.filter((p) => p.configId === configFilter);
    }
    if (activeTags.length === 0) return result;
    return result.filter((p) =>
      activeTags.every((t) => ((p as { tags?: string[] }).tags ?? []).includes(t))
    );
  }, [sorted, activeTags, configFilter]);

  function toggleTag(tag: string) {
    setActiveTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  }

  const deleteMut = useMutation({
    mutationFn: (packageId: string) => deepDeletePackage(packageId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["packages"] });
      setDeleteTarget(null);
    },
  });

  const ggMut = useMutation({
    mutationFn: (id: string) => createGgComponent(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["packages"] }),
  });

  const isFetching = isFetchingPackages || isFetchingConfigs;

  function handleRefresh() {
    refetchPackages();
    refetchConfigs();
  }

  return (
    <div className="p-8 max-w-[1440px] mx-auto space-y-6">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Launch Packages</h1>
        <div className="flex items-center gap-2">
          <RefreshButton
            onClick={handleRefresh}
            loading={isFetching}
            title="Refresh packages & configs"
          />
          <button
            className="btn btn-primary"
            onClick={() => navigate("/")}
          >
            + New Package (via Config)
          </button>
        </div>
      </div>

      {isLoading && <p className="text-slate-500 text-sm">Loading…</p>}

      {!isLoading && packages.length === 0 && (
        <p className="text-slate-500 text-sm italic">
          No launch packages yet. Create one from a config.
        </p>
      )}

      {/* ── Config filter banner ───────────────────────────────────────────── */}
      {configFilter && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-950/40 border border-teal-800/40 text-xs text-teal-300">
          <span>Filtered by config:</span>
          <span className="font-mono text-teal-200">
            {configNameMap[configFilter] ?? configFilter}
          </span>
          <button
            type="button"
            className="ml-auto text-teal-500 hover:text-teal-200 transition-colors"
            onClick={() => {
              setConfigFilter(null);
              navigate("/packages", { replace: true });
            }}
          >
            ✕ clear
          </button>
        </div>
      )}

      {/* ── Tag filter ─────────────────────────────────────────────────────── */}
      {sorted.length > 0 && allTags.length > 0 && (
        <TagFilter
          allTags={allTags}
          activeTags={activeTags}
          onToggle={toggleTag}
          onClear={() => setActiveTags([])}
          total={sorted.length}
          filtered={tagFiltered.length}
        />
      )}

      {/* ── Packages table ─────────────────────────────────────────────────── */}
      {sorted.length > 0 && (
        <div className="card overflow-hidden p-0">
          <table className="table-base">
            <thead>
              <tr>
                <SortableHeader column="packageId" label="Package ID" sort={sort} onToggle={toggle} />
                <SortableHeader column="config"    label="Config"     sort={sort} onToggle={toggle} />
                <SortableHeader column="status"    label="Status"     sort={sort} onToggle={toggle} />
                <th>Live</th>
                <SortableHeader column="lastSeen"  label="Last Seen"  sort={sort} onToggle={toggle} />
                <SortableHeader column="created"   label="Created"    sort={sort} onToggle={toggle} />
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {tagFiltered.map((pkg) => (
                <tr
                  key={pkg.packageId}
                  className="cursor-pointer"
                  onClick={() => navigate(`/packages/${pkg.packageId}`)}
                >
                  <td className="font-mono text-xs text-slate-300">
                    {pkg.packageId}
                  </td>
                  <td>
                    {pkg._configName && (
                      <div className="text-sm font-medium text-slate-200">
                        {pkg._configName}
                      </div>
                    )}
                    <div className="text-xs text-slate-500 font-mono truncate max-w-[160px]">
                      {pkg.configId}
                    </div>
                    <div className="text-xs text-slate-500 font-mono truncate max-w-[160px]">
                      {pkg.configVersion}
                    </div>
                    {(pkg as { tags?: string[] }).tags && (pkg as { tags?: string[] }).tags!.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {(pkg as { tags?: string[] }).tags!.map((tag) => (
                          <span
                            key={tag}
                            className="inline-flex px-1.5 py-0.5 rounded bg-sky-900/30 text-sky-400 text-[10px] font-medium ring-1 ring-sky-800/40"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td>
                    <StatusBadge status={pkg.status} />
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <HeartbeatStatusLed packageId={pkg.packageId} compact />
                  </td>
                  <td className="text-xs text-slate-500">
                    {pkg.lastHeartbeatAt
                      ? new Date(pkg.lastHeartbeatAt).toLocaleTimeString()
                      : "—"}
                  </td>
                  <td className="text-xs text-slate-500">
                    {new Date(pkg.createdAt).toLocaleDateString()}
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center gap-1">
                      <button
                        className="btn btn-ghost text-xs"
                        onClick={() => navigate(`/packages/${pkg.packageId}/logs`)}
                      >
                        Logs
                      </button>
                      <button
                        className="btn btn-ghost text-xs"
                        disabled={pkg.status !== "READY" || ggMut.isPending}
                        onClick={() => ggMut.mutate(pkg.packageId)}
                        title="Create Greengrass v2 component"
                      >
                        GG
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Danger Zone ────────────────────────────────────────────────────── */}
      {packages.length > 0 && (
        <div className="border border-red-900/50 rounded-lg overflow-hidden">
          <button
            className="w-full flex items-center justify-between px-4 py-3 bg-red-950/30 hover:bg-red-950/50 transition-colors text-left"
            onClick={() => setDangerOpen((o) => !o)}
          >
            <span className="flex items-center gap-2 text-sm font-semibold text-red-400">
              <span>⚠</span>
              <span>Danger Zone</span>
            </span>
            <span className="text-slate-500 text-xs">{dangerOpen ? "▲ collapse" : "▼ expand"}</span>
          </button>

          {dangerOpen && (
            <div className="p-4 space-y-3 bg-red-950/10">
              <p className="text-xs text-slate-400">
                Permanently destroys <strong className="text-slate-300">all AWS resources</strong> provisioned
                for each package and removes the database record: IoT Thing &amp; certificate, IoT policy,
                role alias, IAM edge role, CloudWatch log group. S3 assets are retained.
              </p>
              <div className="divide-y divide-red-900/30">
                {packages.map((pkg) => (
                  <div
                    key={pkg.packageId}
                    className="flex items-center justify-between py-2 gap-3"
                  >
                    <div className="min-w-0">
                      <div className="font-mono text-xs text-slate-300 truncate">
                        {pkg.packageId}
                      </div>
                      {pkg._configName && (
                        <div className="text-xs text-slate-500">{pkg._configName}</div>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        className="btn btn-ghost text-xs text-red-300 hover:text-red-200 border border-red-700/70 bg-red-950/30"
                        onClick={() => setDeleteTarget(pkg.packageId)}
                      >
                        🗑 Delete Package
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Confirm dialog ─────────────────────────────────────────────────── */}
      {deleteTarget && (
        <ConfirmDialog
          title="Delete Package"
          message={
            `This will permanently destroy all AWS resources for package "${deleteTarget}":\n\n` +
            `• IoT Thing & certificate\n` +
            `• IoT policy\n` +
            `• IoT role alias\n` +
            `• IAM edge role\n` +
            `• CloudWatch log group\n\n` +
            `The DynamoDB record will also be removed. S3 assets are kept. This action cannot be undone.`
          }
          confirmLabel={deleteMut.isPending ? "Deleting resources…" : "Delete Package"}
          danger
          onConfirm={() => deleteMut.mutate(deleteTarget)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}