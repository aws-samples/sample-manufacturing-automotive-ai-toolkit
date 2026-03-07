import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getPackage,
  getPackageDownloadUrl,
  triggerRemediation,
  getConfig,
  deepDeletePackage,
  updatePackageTags,
} from "../api/client";
import StatusBadge from "../components/StatusBadge";
import PackageControlPanel from "../components/PackageControlPanel";
import ConfirmDialog from "../components/ConfirmDialog";
import TagEditor from "../components/TagEditor";
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

  const [remediating, setRemediating] = useState(false);
  const [remediationResult, setRemediationResult] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
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

  const remediateMut = useMutation({
    mutationFn: () => {
      const end = new Date().toISOString();
      const start = new Date(Date.now() - 15 * 60_000).toISOString();
      return triggerRemediation(packageId!, start, end);
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["package", packageId] });
      setRemediationResult(
        `Remediation complete. New config version: ${res.newConfigVersion}`
      );
      setRemediating(false);
    },
    onError: () => setRemediating(false),
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
                value={pkg.configVersion}
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

            {/* AI Remediation */}
            <div className="card space-y-3">
              <p className="text-xs font-medium text-slate-500">AI-Assisted Remediation</p>
              <p className="text-xs text-slate-400">
                Triggers the Bedrock agent to analyse the last 15 minutes of error logs
                and produce a corrected SFC config version.
              </p>
              {remediationResult && (
                <p className="text-xs text-green-400">{remediationResult}</p>
              )}
              {remediateMut.isError && (
                <p className="text-xs text-red-400">Remediation failed.</p>
              )}
              <button
                className="btn btn-primary"
                disabled={remediating || remediateMut.isPending}
                onClick={() => {
                  setRemediating(true);
                  setRemediationResult(null);
                  remediateMut.mutate();
                }}
              >
                {remediateMut.isPending ? <span className="spinner" /> : "Run AI Remediation"}
              </button>
            </div>

            {/* Danger Zone */}
            <div className="border border-red-900/50 rounded-lg overflow-hidden">
              <div className="px-4 py-3 bg-red-950/30 flex items-center gap-2">
                <span className="text-sm font-semibold text-red-400">⚠ Danger Zone</span>
              </div>
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