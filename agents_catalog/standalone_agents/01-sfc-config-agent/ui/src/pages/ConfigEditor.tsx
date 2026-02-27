import { useState, useEffect } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getConfig,
  saveConfig,
  setFocus,
  listConfigVersions,
  getConfigVersion,
  createPackage,
  getFocus,
  updateConfigTags,
  listPackages,
} from "../api/client";
import MonacoJsonEditor from "../components/MonacoJsonEditor";
import StatusBadge from "../components/StatusBadge";
import TagEditor from "../components/TagEditor";
import { useRef } from "react";

export default function ConfigEditor() {
  const { configId } = useParams<{ configId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [searchParams] = useSearchParams();
  const versionParam = searchParams.get("version") ?? undefined;

  const { data: cfg, isLoading } = useQuery({
    queryKey: ["config", configId],
    queryFn: () => getConfig(configId!),
    enabled: !!configId,
  });

  const { data: focus } = useQuery({ queryKey: ["focus"], queryFn: getFocus });
  const { data: packages } = useQuery({ queryKey: ["packages"], queryFn: listPackages });
  const { data: versions } = useQuery({
    queryKey: ["configVersions", configId],
    queryFn: () => listConfigVersions(configId!),
    enabled: !!configId,
  });

  const [content, setContent] = useState("{}");
  const [selectedVersion, setSelectedVersion] = useState(versionParam ?? "");
  const [editingName, setEditingName] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const tagsRef = useRef<string[]>([]);

  function handleTagChange(newTags: string[]) {
    setTags(newTags);
    tagsRef.current = newTags;
    if (configId) updateConfigTags(configId, newTags).catch(console.error);
  }

  // Load a specific version
  const loadVersionMut = useMutation({
    mutationFn: (v: string) => getConfigVersion(configId!, v),
    onSuccess: (data) => {
      const raw = data.content;
      setContent(typeof raw === "string" ? raw : JSON.stringify(raw, null, 2));
    },
  });

  // When a ?version= param is present, load that specific snapshot immediately
  const versionLoadedRef = useRef(false);
  useEffect(() => {
    if (versionParam && !versionLoadedRef.current && configId) {
      versionLoadedRef.current = true;
      setSelectedVersion(versionParam);
      loadVersionMut.mutate(versionParam);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [versionParam, configId]);

  useEffect(() => {
    // Skip setting content from latest-version query if we're loading a specific version
    if (cfg?.content != null && !versionParam) {
      const raw = cfg.content;
      setContent(
        typeof raw === "string" ? raw : JSON.stringify(raw, null, 2)
      );
    }
    if (cfg?.version && !selectedVersion) setSelectedVersion(cfg.version);
    if (cfg?.name && !editingName) setEditingName(cfg.name);
    if (cfg && !tagsRef.current.length && (cfg as { tags?: string[] }).tags?.length) {
      const t = (cfg as { tags?: string[] }).tags!;
      setTags(t);
      tagsRef.current = t;
    }
  }, [cfg]);

  const saveMut = useMutation({
    mutationFn: () =>
      saveConfig(configId!, {
        name: editingName || cfg?.name || configId!,
        description: cfg?.description,
        content,
        tags,
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

  const isDeployed = (packages ?? []).some((p) => p.configId === configId);

  // Check if a package already exists for the currently selected version
  const existingPackageForVersion = (packages ?? []).find(
    (p) => p.configId === configId && p.configVersion === (selectedVersion || cfg?.version)
  );

  function deriveConfigStatus(): string {
    if (focus?.focusedConfigId === configId) return "focused";
    if (isDeployed) return "deployed";
    return "unused";
  }

  if (isLoading) return <p className="p-6 text-slate-500 text-sm">Loading…</p>;
  if (!cfg) return <p className="p-6 text-slate-500 text-sm">Config not found.</p>;

  return (
    <div className="p-6 max-w-6xl mx-auto flex flex-col gap-4 h-[calc(100vh-7rem)]">
      {/* Toolbar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex flex-col gap-1">
          <input
            className="bg-transparent border border-transparent hover:border-[#2a3044] focus:border-[#4a5568] rounded px-2 py-0.5 text-base font-semibold text-slate-100 outline-none transition-colors w-56"
            value={editingName}
            onChange={(e) => setEditingName(e.target.value)}
            onBlur={() => { if (!editingName.trim()) setEditingName(cfg.name); }}
            title="Click to edit config name"
            placeholder="Config name"
          />
          <p className="text-xs text-slate-500 font-mono px-2">{configId}</p>
        </div>

        {/* Tags */}
        <div className="w-64">
          <TagEditor tags={tags} onChange={handleTagChange} placeholder="Add tag…" />
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
          {(() => {
            const s = deriveConfigStatus();
            if (s === "deployed") {
              const pkgs = (packages ?? []).filter((p) => p.configId === configId);
              const dest = pkgs.length === 1
                ? `/packages/${pkgs[0].packageId}`
                : `/packages?configId=${configId}`;
              return (
                <button
                  type="button"
                  className="hover:opacity-80 transition-opacity"
                  onClick={() => navigate(dest)}
                  title={pkgs.length === 1 ? `Go to package` : `Show ${pkgs.length} packages`}
                >
                  <StatusBadge status="deployed" />
                </button>
              );
            }
            return <StatusBadge status={s} />;
          })()}

          <button
            className="btn btn-secondary"
            disabled={focusMut.isPending || isFocused}
            onClick={() => focusMut.mutate()}
            title="Set this version as the active focus for launch packages"
          >
            {focusMut.isPending ? <span className="spinner" /> : "Set as Focus"}
          </button>

          {existingPackageForVersion ? (
            <button
              type="button"
              className="btn btn-secondary text-teal-300 border-teal-700/50"
              onClick={() => navigate(`/packages/${existingPackageForVersion.packageId}`)}
              title={`Package already exists for this config version — click to open`}
            >
              Package exists ↗
            </button>
          ) : (
            <button
              className="btn btn-secondary disabled:opacity-40 disabled:cursor-not-allowed"
              disabled={packageMut.isPending || !isFocused}
              onClick={() => packageMut.mutate()}
              title={isFocused ? "Create a launch package from this focused config version" : "Set this version as Focus first to create a launch package"}
            >
              {packageMut.isPending ? <span className="spinner" /> : "Create Launch Package"}
            </button>
          )}

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