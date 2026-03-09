import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getControlState,
  setTelemetry,
  setDiagnostics,
  pushConfigUpdate,
  restartSfc,
  getConfig,
  listConfigVersions,
  type LaunchPackage,
} from "../api/client";
import ConfirmDialog from "./ConfirmDialog";
import HeartbeatStatusLed from "./HeartbeatStatusLed";
import { useNavigate } from "react-router-dom";

interface Props {
  pkg: LaunchPackage;
}

/**
 * Toggle row matching design spec:
 *   Telemetry (OTEL)   ● ON  ○ OFF   [Apply]
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

  // Sync local when persisted value changes (e.g. after Apply succeeds)
  useState(() => { setLocal(value); });

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
  const navigate = useNavigate();
  const isReady = pkg.status === "READY";

  const { data: ctrl } = useQuery({
    queryKey: ["control", pkg.packageId],
    queryFn: () => getControlState(pkg.packageId),
    enabled: isReady,
  });

  // Config push state — locked to the package's own configId
  const [pushVersion, setPushVersion] = useState("");
  const { data: configMeta } = useQuery({
    queryKey: ["config", pkg.configId],
    queryFn: () => getConfig(pkg.configId),
    enabled: !!pkg.configId,
  });
  const { data: allVersions } = useQuery({
    queryKey: ["configVersions", pkg.configId],
    queryFn: () => listConfigVersions(pkg.configId),
    enabled: !!pkg.configId,
  });
  // Only show versions strictly newer than the one snapshotted into the package
  const newerVersions = (allVersions ?? []).filter(
    (v) => v.version > pkg.configVersion
  );

  // Restart confirm
  const [showRestartConfirm, setShowRestartConfirm] = useState(false);

  // Mutations
  const telemetryMut = useMutation({
    mutationFn: (v: boolean) => setTelemetry(pkg.packageId, v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["control", pkg.packageId] }),
  });
  const diagMut = useMutation({
    mutationFn: (v: boolean) => setDiagnostics(pkg.packageId, v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["control", pkg.packageId] }),
  });
  const cfgPushMut = useMutation({
    mutationFn: () => pushConfigUpdate(pkg.packageId, pkg.configId, pushVersion),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["control", pkg.packageId] }),
  });
  const restartMut = useMutation({
    mutationFn: () => restartSfc(pkg.packageId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["control", pkg.packageId] }),
  });

  const telemetry = ctrl?.telemetryEnabled === true || ctrl?.telemetryEnabled === "unknown";
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

      {/* Toggles */}
      <div className="card space-y-1">
        <p className="text-xs font-medium text-slate-500 mb-2">Runtime Controls</p>
        <Toggle
          label="Telemetry (OTEL)"
          value={telemetry}
          onApply={(v) => telemetryMut.mutate(v)}
          disabled={!isReady}
          pending={telemetryMut.isPending}
        />
        <Toggle
          label="Diagnostics (TRACE log)"
          value={diagnostics}
          onApply={(v) => diagMut.mutate(v)}
          disabled={!isReady}
          pending={diagMut.isPending}
        />
      </div>

      {/* Push config update */}
      <div className="card space-y-3">
        <p className="text-xs font-medium text-slate-500">Push Config Update</p>
        <div className="space-y-2">
          {/* Config locked to the package's own configId */}
          <div className="rounded px-2 py-1.5 bg-[#0f1117] border border-[#2a3044]">
            <p className="text-[10px] text-slate-500 mb-0.5">Config (locked)</p>
            <p className="text-xs text-slate-300 font-mono truncate">
              {configMeta?.name ?? pkg.configId}
            </p>
          </div>
          {newerVersions.length === 0 ? (
            <p className="text-xs text-slate-500 italic border border-slate-700 rounded px-3 py-2">
              No newer versions available — save a new version of this config first.
            </p>
          ) : (
            <select
              className="w-full bg-[#0f1117] border border-[#2a3044] rounded px-2 py-1.5 text-sm text-slate-300 disabled:opacity-40"
              value={pushVersion}
              onChange={(e) => setPushVersion(e.target.value)}
              disabled={!isReady}
            >
              <option value="">Select version…</option>
              {newerVersions.map((v) => (
                <option key={v.version} value={v.version}>
                  {new Date(v.version).toLocaleString()}
                </option>
              ))}
            </select>
          )}
          <button
            className="btn btn-primary w-full"
            disabled={!isReady || !pushVersion || cfgPushMut.isPending}
            onClick={() => cfgPushMut.mutate()}
          >
            {cfgPushMut.isPending ? <span className="spinner" /> : "Push Update"}
          </button>
          {cfgPushMut.isSuccess && (
            <p className="text-xs text-green-400">Config update dispatched.</p>
          )}
          {ctrl?.lastConfigUpdateAt && (
            <p className="text-xs text-slate-600">
              Last push: {ctrl.lastConfigUpdateVersion} at{" "}
              {new Date(ctrl.lastConfigUpdateAt).toLocaleString()}
            </p>
          )}
        </div>
      </div>

      {/* Restart */}
      <div className="card space-y-2">
        <p className="text-xs font-medium text-slate-500">Restart SFC Runtime</p>
        <button
          className="btn btn-danger w-full"
          disabled={!isReady || restartMut.isPending}
          onClick={() => setShowRestartConfirm(true)}
        >
          {restartMut.isPending ? <span className="spinner" /> : "Restart SFC"}
        </button>
        {ctrl?.lastRestartAt && (
          <p className="text-xs text-slate-600">
            Last restart: {new Date(ctrl.lastRestartAt).toLocaleString()}
          </p>
        )}
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