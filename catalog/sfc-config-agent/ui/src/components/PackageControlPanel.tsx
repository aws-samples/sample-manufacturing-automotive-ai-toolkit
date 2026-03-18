import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getControlState,
  setDiagnostics,
  pushConfigUpdate,
  restartSfc,
  listConfigs,
  listConfigVersions,
  type LaunchPackage,
} from "../api/client";
import ConfirmDialog from "./ConfirmDialog";
import HeartbeatStatusLed from "./HeartbeatStatusLed";

interface Props {
  pkg: LaunchPackage;
}

/**
 * Toggle row:
 *   Diagnostics (TRACE log)   ● ON  ○ OFF   [Apply]
 * Radio buttons select local state; Apply fires the mutation.
 */
function Toggle({
  label,
  value,
  onApply,
  disabled,
  pending,
}: {
  label: string;
  value: boolean;
  onApply: (v: boolean) => void;
  disabled: boolean;
  pending: boolean;
}) {
  const [local, setLocal] = useState(value);

  // Sync local whenever the persisted server value changes
  // (page refresh, Apply success, or external update)
  useEffect(() => { setLocal(value); }, [value]);

  const dirty = local !== value;

  return (
    <div className="flex items-center justify-between py-2 gap-3">
      <span className="text-sm text-slate-300 shrink-0">{label}</span>
      <div className="flex items-center gap-3 ml-auto">
        <label className="flex items-center gap-1.5 text-sm cursor-pointer">
          <input
            type="radio"
            checked={local}
            onChange={() => setLocal(true)}
            disabled={disabled || pending}
            className="accent-sky-500"
          />
          ON
        </label>
        <label className="flex items-center gap-1.5 text-sm cursor-pointer">
          <input
            type="radio"
            checked={!local}
            onChange={() => setLocal(false)}
            disabled={disabled || pending}
            className="accent-sky-500"
          />
          OFF
        </label>
        <button
          className="btn btn-secondary text-xs py-1 px-2"
          disabled={disabled || pending || !dirty}
          onClick={() => onApply(local)}
        >
          {pending ? <span className="spinner" /> : dirty ? "Apply" : "✓"}
        </button>
      </div>
    </div>
  );
}

export default function PackageControlPanel({ pkg }: Props) {
  const qc = useQueryClient();
  const isReady = pkg.status === "READY";

  const { data: ctrl } = useQuery({
    queryKey: ["control", pkg.packageId],
    queryFn: () => getControlState(pkg.packageId),
    enabled: isReady,
  });

  // Config push state — any config, any version
  const { data: allConfigs } = useQuery({
    queryKey: ["configs"],
    queryFn: listConfigs,
  });
  const [pushConfigId, setPushConfigId] = useState(pkg.configId);
  const [pushVersion, setPushVersion] = useState("");

  const { data: pushConfigVersions } = useQuery({
    queryKey: ["configVersions", pushConfigId],
    queryFn: () => listConfigVersions(pushConfigId),
    enabled: !!pushConfigId,
  });

  // Build a vN label map: oldest version = v1, next = v2, …
  const versionLabelMap: Record<string, string> = Object.fromEntries(
    [...(pushConfigVersions ?? [])].reverse().map((v, idx) => [v.version, `v${idx + 1}`])
  );

  // Restart confirm
  const [showRestartConfirm, setShowRestartConfirm] = useState(false);

  // Mutations
  const diagMut = useMutation({
    mutationFn: (v: boolean) => setDiagnostics(pkg.packageId, v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["control", pkg.packageId] }),
  });
  const cfgPushMut = useMutation({
    mutationFn: () => pushConfigUpdate(pkg.packageId, pushConfigId, pushVersion),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["package", pkg.packageId] });
      qc.invalidateQueries({ queryKey: ["packages"] });
      qc.invalidateQueries({ queryKey: ["configs"] });
      qc.invalidateQueries({ queryKey: ["control", pkg.packageId] });
    },
  });
  const restartMut = useMutation({
    mutationFn: () => restartSfc(pkg.packageId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["control", pkg.packageId] }),
  });

  const diagnostics = ctrl?.diagnosticsEnabled === true;

  return (
    <div className="space-y-4">
      {/* Live status */}
      <HeartbeatStatusLed packageId={pkg.packageId} />

      {!isReady && (
        <p className="text-xs text-slate-500 italic border border-slate-700 rounded px-3 py-2">
          Controls are disabled — package must be in READY state (current:{" "}
          {pkg.status}).
        </p>
      )}

      {/* Runtime Controls — Diagnostics toggle + Restart */}
      <div className="card space-y-1">
        <p className="text-xs font-medium text-slate-500 mb-2">Runtime Controls</p>

        <Toggle
          label="Diagnostics (TRACE log)"
          value={diagnostics}
          onApply={(v) => diagMut.mutate(v)}
          disabled={!isReady}
          pending={diagMut.isPending}
        />

        <div className="pt-1 border-t border-slate-700/60">
          <div className="flex items-center justify-between gap-3 py-1.5">
            <span className="text-sm text-slate-300 shrink-0">Restart SFC</span>
            <button
              className="btn btn-danger text-xs py-1 px-3"
              disabled={!isReady || restartMut.isPending}
              onClick={() => setShowRestartConfirm(true)}
            >
              {restartMut.isPending ? <span className="spinner" /> : "Restart"}
            </button>
          </div>
          {ctrl?.lastRestartAt && (
            <p className="text-xs text-slate-600 mt-0.5">
              Last restart: {new Date(ctrl.lastRestartAt).toLocaleString()}
            </p>
          )}
        </div>
      </div>

      {/* Push config update */}
      <div className="card space-y-3">
        <p className="text-xs font-medium text-slate-500">Push Config Update</p>
        <div className="space-y-2">
          {/* Config selector — any config */}
          <select
            className="w-full bg-[#0f1117] border border-[#2a3044] rounded px-2 py-1.5 text-sm text-slate-300 disabled:opacity-40"
            value={pushConfigId}
            onChange={(e) => {
              setPushConfigId(e.target.value);
              setPushVersion("");
            }}
            disabled={!isReady}
          >
            {(allConfigs ?? []).map((c) => (
              <option key={c.configId} value={c.configId}>
                {c.name || c.configId}
              </option>
            ))}
          </select>

          {/* Version selector — all versions of selected config */}
          {(pushConfigVersions ?? []).length === 0 ? (
            <p className="text-xs text-slate-500 italic border border-slate-700 rounded px-3 py-2">
              No versions available for this config.
            </p>
          ) : (
            <select
              className="w-full bg-[#0f1117] border border-[#2a3044] rounded px-2 py-1.5 text-sm text-slate-300 disabled:opacity-40"
              value={pushVersion}
              onChange={(e) => setPushVersion(e.target.value)}
              disabled={!isReady}
            >
              <option value="">Select version…</option>
              {(pushConfigVersions ?? []).map((v) => (
                <option key={v.version} value={v.version}>
                  {versionLabelMap[v.version] ? `${versionLabelMap[v.version]} — ` : ""}
                  {v.version}
                </option>
              ))}
            </select>
          )}

          <button
            className="btn btn-primary w-full"
            disabled={!isReady || !pushVersion || cfgPushMut.isPending}
            onClick={() => cfgPushMut.mutate()}
          >
            {cfgPushMut.isPending ? <span className="spinner" /> : "Push to Edge"}
          </button>
          {cfgPushMut.isSuccess && (
            <p className="text-xs text-green-400">Config push dispatched — LP record updated.</p>
          )}
          {ctrl?.lastConfigUpdateAt && (
            <p className="text-xs text-slate-600">
              Last push: {ctrl.lastConfigUpdateVersion} at{" "}
              {new Date(ctrl.lastConfigUpdateAt).toLocaleString()}
            </p>
          )}
        </div>
      </div>

      {showRestartConfirm && (
        <ConfirmDialog
          title="Restart SFC Runtime"
          message={`This will send a restart command to the edge device running package ${pkg.packageId}. The SFC process will be interrupted briefly.`}
          confirmLabel="Restart"
          danger
          onConfirm={() => {
            setShowRestartConfirm(false);
            restartMut.mutate();
          }}
          onCancel={() => setShowRestartConfirm(false)}
        />
      )}
    </div>
  );
}
