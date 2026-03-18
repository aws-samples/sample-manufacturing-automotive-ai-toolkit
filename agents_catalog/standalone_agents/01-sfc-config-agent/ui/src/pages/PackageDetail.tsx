import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getPackage,
  getPackageDownloadUrl,
  getConfig,
  listConfigVersions,
  deepDeletePackage,
  updatePackageTags,
} from "../api/client";
import StatusBadge from "../components/StatusBadge";
import PackageControlPanel from "../components/PackageControlPanel";
import ConfirmDialog from "../components/ConfirmDialog";
import GgDeployDialog from "../components/GgDeployDialog";
import TagEditor from "../components/TagEditor";
import MetricsDashboard from "../components/MetricsDashboard";
import { useState, useEffect, useRef } from "react";

export default function PackageDetail() {
  const { packageId } = useParams<{ packageId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: pkg, isLoading } = useQuery({
    queryKey: ["package", packageId],
    queryFn: () => getPackage(packageId!),
    enabled: !!packageId,
    refetchInterval: 20_000,
  });

  const { data: configMeta } = useQuery({
    queryKey: ["config", pkg?.configId],
    queryFn: () => getConfig(pkg!.configId),
    enabled: !!pkg?.configId,
  });

  const { data: configVersions } = useQuery({
    queryKey: ["configVersions", pkg?.configId],
    queryFn: () => listConfigVersions(pkg!.configId),
    enabled: !!pkg?.configId,
  });

  // Compute vN label for the snapshotted config version (oldest = v1)
  const versionLabel = (() => {
    if (!configVersions || !pkg?.configVersion) return null;
    const ordered = [...configVersions].reverse(); // oldest first
    const idx = ordered.findIndex((v) => v.version === pkg.configVersion);
    return idx >= 0 ? `v${idx + 1}` : null;
  })();

  const [confirmDelete, setConfirmDelete] = useState(false);
  const [ggConfirmOpen, setGgConfirmOpen] = useState(false);
  const [dangerZoneOpen, setDangerZoneOpen] = useState(false);
  const [tags, setTags] = useState<string[]>([]);
  const tagsInitialized = useRef(false);

  useEffect(() => {
    if (pkg && !tagsInitialized.current) {
      setTags((pkg as { tags?: string[] }).tags ?? []);
      tagsInitialized.current = true;
    }
  }, [pkg]);

  function handleTagChange(newTags: string[]) {
    setTags(newTags);
    updatePackageTags(packageId!, newTags).catch(console.error);
  }

  const deleteMut = useMutation({
    mutationFn: () => deepDeletePackage(packageId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["packages"] });
      navigate("/packages");
    },
  });

  if (isLoading) return <p className="p-6 text-slate-500 text-sm">Loading…</p>;
  if (!pkg) return <p className="p-6 text-slate-500 text-sm">Package not found.</p>;

  return (
    <>
      <div className="p-8 max-w-[1440px] mx-auto">
        <div className="flex items-center gap-3 mb-6 flex-wrap">
          <button className="btn btn-ghost text-xs" onClick={() => navigate("/packages")}>
            ← Packages
          </button>
          <h1 className="text-base font-semibold font-mono">{pkg.packageId}</h1>
          <StatusBadge status={pkg.status} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: metadata */}
          <div className="lg:col-span-2 space-y-4">
            {/* Info card */}
            <div className="card space-y-3">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-medium text-slate-500">Package Info</p>
              </div>
              <div className="mb-3">
                <p className="text-xs text-slate-500 mb-1">Tags</p>
                <TagEditor tags={tags} onChange={handleTagChange} placeholder="Add tag…" />
              </div>
              {configMeta?.name && configMeta.name !== pkg.configId && (
                <Row
                  label="Config Name"
                  value={configMeta.name}
                  prominent
                  onClick={() =>
                    navigate(
                      `/configs/${pkg.configId}?version=${encodeURIComponent(pkg.configVersion)}`
                    )
                  }
                  title="Open the exact config version snapshotted into this zip"
                />
              )}
              <Row label="Config ID" value={pkg.configId} mono />
              <Row
                label="Config Version"
                value={versionLabel ? `${versionLabel} — ${pkg.configVersion}` : pkg.configVersion}
                mono
                sublabel="snapshotted into zip"
                onClick={() =>
                  navigate(
                    `/configs/${pkg.configId}?version=${encodeURIComponent(pkg.configVersion)}`
                  )
                }
                title="Open this exact config version in the editor"
              />
              <Row label="Created" value={new Date(pkg.createdAt).toLocaleString()} />
              {pkg.iotThingName && <Row label="IoT Thing" value={pkg.iotThingName} mono />}
              {pkg.iamRoleArn && <Row label="IAM Role" value={pkg.iamRoleArn} mono />}
              {pkg.logGroupName && <Row label="Log Group" value={pkg.logGroupName} mono />}
              {pkg.ggComponentArn && (
                <Row label="GG Component" value={pkg.ggComponentArn} mono />
              )}
            </div>

            {/* Download card */}
            {pkg.s3ZipKey && (
              <div className="card flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">Launch Bundle</p>
                  <p className="text-xs text-slate-500 font-mono">{pkg.s3ZipKey}</p>
                </div>
                <DownloadButton packageId={pkg.packageId} />
              </div>
            )}

            {/* CloudWatch Metrics Dashboard */}
            <MetricsDashboard packageId={pkg.packageId} />

            {/* AI Remediation entry point */}
            <div className="card space-y-3 border border-sky-900/40 bg-sky-950/10">
              <div className="flex items-center gap-2">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="w-4 h-4 text-sky-400 shrink-0"
                >
                  <polyline points="2,20 9,7 13,13 16,9 22,20" />
                  <polyline points="14.3,11 16,9 17.7,11.4" />
                </svg>
                <p className="text-xs font-medium text-sky-300">AI-Assisted Remediation</p>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Open the Log Viewer to inspect live SFC logs. When errors are detected,
                the <span className="text-sky-300 font-medium">Fix with AI</span> button
                triggers a <span className="text-slate-300">Bedrock AgentCore Runtime</span> that
                analyses the error window and produces a corrected config version automatically.
              </p>
              <button
                className="btn btn-primary inline-flex items-center gap-2"
                onClick={() => navigate(`/packages/${pkg.packageId}/logs`)}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="w-3.5 h-3.5 shrink-0"
                >
                  <polyline points="2,20 9,7 13,13 16,9 22,20" />
                  <polyline points="14.3,11 16,9 17.7,11.4" />
                </svg>
                Open Remediation Area
              </button>
            </div>

            {/* Greengrass Deployment */}
            <div className="card space-y-3 border border-slate-700/50">
              <p className="text-xs font-medium text-slate-400">Greengrass Deployment</p>
              <p className="text-xs text-slate-400 leading-relaxed">
                Publish this launch bundle as a new{" "}
                <span className="text-slate-300 font-medium">AWS IoT Greengrass v2 component version</span>.
                Each call creates a new version (timestamped{" "}
                <span className="font-mono text-slate-300">YYYY.MM.DD.HHmmss</span>) under the component
                name <span className="font-mono text-slate-300">com.sfc.&lt;configId&gt;</span> — versions
                accumulate and nothing is overwritten. The resulting component ARN can be targeted in a
                Greengrass deployment to roll out SFC to any edge device managed by the local Greengrass
                nucleus.
                {pkg.ggComponentArn && (
                  <span className="block mt-2 text-emerald-400/80 font-mono text-[10px] break-all">
                    ✓ latest: {pkg.ggComponentArn}
                  </span>
                )}
              </p>
              <button
                className="inline-flex items-center px-3 py-1.5 rounded-md text-xs font-medium
                  border border-slate-600/70 text-slate-300 hover:text-slate-100 hover:border-slate-500
                  transition-colors bg-transparent disabled:opacity-40 disabled:cursor-not-allowed"
                disabled={pkg.status !== "READY"}
                onClick={() => setGgConfirmOpen(true)}
              >
                Create Greengrass Component
              </button>
            </div>

            {/* Danger Zone */}
            <div className="border border-red-900/50 rounded-lg overflow-hidden">
              <button
                className="w-full flex items-center justify-between px-4 py-3 bg-red-950/30 hover:bg-red-950/50 transition-colors text-left"
                onClick={() => setDangerZoneOpen((o) => !o)}
              >
                <span className="flex items-center gap-2 text-sm font-semibold text-red-400">
                  <span>⚠</span>
                  <span>Danger Zone</span>
                </span>
                <span className="text-slate-500 text-xs">
                  {dangerZoneOpen ? "▲ collapse" : "▼ expand"}
                </span>
              </button>
              {dangerZoneOpen && (
                <div className="p-4 space-y-3 bg-red-950/10">
                  <p className="text-xs text-slate-400">
                    Permanently destroys <strong className="text-slate-300">all AWS resources</strong> provisioned
                    for this package and removes the database record:{" "}
                    IoT Thing &amp; certificate, IoT policy, role alias, IAM edge role,
                    CloudWatch log group. S3 assets are retained.
                  </p>
                  <button
                    className="btn btn-ghost text-xs text-red-300 hover:text-red-200 border border-red-700/70 bg-red-950/30"
                    onClick={() => setConfirmDelete(true)}
                  >
                    🗑 Delete Package
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Right: control panel */}
          <div>
            <PackageControlPanel pkg={pkg} />
          </div>
        </div>
      </div>

      {/* Delete confirmation dialog */}
      {confirmDelete && (
        <ConfirmDialog
          title="Delete Package"
          message={
            `This will permanently destroy all AWS resources for package "${pkg.packageId}":\n\n` +
            `• IoT Thing & certificate\n` +
            `• IoT policy\n` +
            `• IoT role alias\n` +
            `• IAM edge role\n` +
            `• CloudWatch log group\n\n` +
            `The DynamoDB record will also be removed. S3 assets are kept. This action cannot be undone.`
          }
          confirmLabel={deleteMut.isPending ? "Deleting resources…" : "Delete Package"}
          danger
          onConfirm={() => deleteMut.mutate()}
          onCancel={() => setConfirmDelete(false)}
        />
      )}

      {/* Greengrass confirmation dialog — shared component */}
      {ggConfirmOpen && (
        <GgDeployDialog
          packageId={pkg.packageId}
          onClose={() => setGgConfirmOpen(false)}
        />
      )}
    </>
  );
}

function Row({
  label,
  value,
  mono = false,
  prominent = false,
  onClick,
  title,
  sublabel,
}: {
  label: string;
  value: string;
  mono?: boolean;
  prominent?: boolean;
  onClick?: () => void;
  title?: string;
  sublabel?: string;
}) {
  const textSize = prominent ? "text-sm" : "text-xs";
  return (
    <div className="flex items-start gap-2">
      <span className="w-32 shrink-0 text-slate-500 text-xs pt-0.5">{label}</span>
      <div className="flex flex-col gap-0.5 min-w-0">
        {onClick ? (
          <button
            type="button"
            onClick={onClick}
            title={title}
            className={`break-all text-left cursor-pointer ${textSize} text-sky-400 hover:text-sky-300 hover:underline transition-colors ${
              mono ? "font-mono" : ""
            }`}
          >
            {value}
          </button>
        ) : (
          <span
            className={`break-all ${textSize} ${mono ? "font-mono text-slate-300" : "text-slate-200"}`}
          >
            {value}
          </span>
        )}
        {sublabel && (
          <span className="text-[10px] text-slate-500 italic">{sublabel}</span>
        )}
      </div>
    </div>
  );
}

function DownloadButton({ packageId }: { packageId: string }) {
  const [loading, setLoading] = useState(false);

  async function handleDownload() {
    setLoading(true);
    try {
      const url = await getPackageDownloadUrl(packageId);
      window.open(url, "_blank");
    } finally {
      setLoading(false);
    }
  }

  return (
    <button className="btn btn-secondary" onClick={handleDownload} disabled={loading}>
      {loading ? <span className="spinner" /> : "Download ZIP"}
    </button>
  );
}
