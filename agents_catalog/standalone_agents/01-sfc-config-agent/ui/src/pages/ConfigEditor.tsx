import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getConfig,
  saveConfig,
  setFocus,
  listConfigVersions,
  getConfigVersion,
  createPackage,
  getFocus,
} from "../api/client";
import MonacoJsonEditor from "../components/MonacoJsonEditor";
import StatusBadge from "../components/StatusBadge";

export default function ConfigEditor() {
  const { configId } = useParams<{ configId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: cfg, isLoading } = useQuery({
    queryKey: ["config", configId],
    queryFn: () => getConfig(configId!),
    enabled: !!configId,
  });

  const { data: focus } = useQuery({ queryKey: ["focus"], queryFn: getFocus });
  const { data: versions } = useQuery({
    queryKey: ["configVersions", configId],
    queryFn: () => listConfigVersions(configId!),
    enabled: !!configId,
  });

  const [content, setContent] = useState("{}");
  const [selectedVersion, setSelectedVersion] = useState("");

  useEffect(() => {
    if (cfg?.content) setContent(cfg.content);
    if (cfg?.version && !selectedVersion) setSelectedVersion(cfg.version);
  }, [cfg]);

  // Load a specific version
  const loadVersionMut = useMutation({
    mutationFn: (v: string) => getConfigVersion(configId!, v),
    onSuccess: (data) => setContent(data.content),
  });

  const saveMut = useMutation({
    mutationFn: () =>
      saveConfig(configId!, {
        name: cfg?.name ?? configId!,
        description: cfg?.description,
        content,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["config", configId] });
      qc.invalidateQueries({ queryKey: ["configVersions", configId] });
      qc.invalidateQueries({ queryKey: ["configs"] });
    },
  });

  const focusMut = useMutation({
    mutationFn: () => setFocus(configId!, selectedVersion || cfg?.version || ""),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["focus"] }),
  });

  const packageMut = useMutation({
    mutationFn: () =>
      createPackage({
        configId: configId!,
        configVersion: selectedVersion || cfg?.version || "",
      }),
    onSuccess: (pkg) => navigate(`/packages/${pkg.packageId}`),
  });

  const isFocused =
    focus?.focusedConfigId === configId &&
    focus?.focusedConfigVersion === (selectedVersion || cfg?.version);

  if (isLoading) return <p className="p-6 text-slate-500 text-sm">Loading…</p>;
  if (!cfg) return <p className="p-6 text-slate-500 text-sm">Config not found.</p>;

  return (
    <div className="p-6 max-w-6xl mx-auto flex flex-col gap-4 h-[calc(100vh-7rem)]">
      {/* Toolbar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div>
          <h1 className="text-base font-semibold">{cfg.name}</h1>
          <p className="text-xs text-slate-500 font-mono">{configId}</p>
        </div>

        {/* Version picker */}
        {versions && versions.length > 1 && (
          <select
            className="bg-[#0f1117] border border-[#2a3044] rounded px-2 py-1 text-xs text-slate-300"
            value={selectedVersion}
            onChange={(e) => {
              setSelectedVersion(e.target.value);
              loadVersionMut.mutate(e.target.value);
            }}
          >
            {versions.map((v) => (
              <option key={v.version} value={v.version}>
                {v.version}
              </option>
            ))}
          </select>
        )}

        <div className="flex items-center gap-2 ml-auto flex-wrap">
          <StatusBadge status={cfg.status} />

          {isFocused && (
            <span className="badge badge-info">In Focus</span>
          )}

          <button
            className="btn btn-secondary"
            disabled={focusMut.isPending || isFocused}
            onClick={() => focusMut.mutate()}
            title="Set this version as the active focus for launch packages"
          >
            {focusMut.isPending ? <span className="spinner" /> : "Set as Focus"}
          </button>

          <button
            className="btn btn-secondary"
            disabled={packageMut.isPending}
            onClick={() => packageMut.mutate()}
          >
            {packageMut.isPending ? <span className="spinner" /> : "Create Launch Package"}
          </button>

          <button
            className="btn btn-primary"
            disabled={saveMut.isPending}
            onClick={() => saveMut.mutate()}
          >
            {saveMut.isPending ? <span className="spinner" /> : "Save New Version"}
          </button>
        </div>
      </div>

      {saveMut.isSuccess && (
        <p className="text-xs text-green-400">Saved as new version.</p>
      )}

      {/* Editor */}
      <div className="flex-1 min-h-0">
        <MonacoJsonEditor
          value={content}
          onChange={setContent}
          height="100%"
        />
      </div>
    </div>
  );
}