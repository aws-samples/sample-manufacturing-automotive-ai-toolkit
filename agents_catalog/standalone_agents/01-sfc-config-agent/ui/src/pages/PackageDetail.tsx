import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getPackage, getPackageDownloadUrl, triggerRemediation, getConfig } from "../api/client";
import StatusBadge from "../components/StatusBadge";
import PackageControlPanel from "../components/PackageControlPanel";
import { useState } from "react";

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
    <div className="p-6 max-w-7xl mx-auto">
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
            <p className="text-xs font-medium text-slate-500 mb-1">Package Info</p>
            {configMeta?.name && configMeta.name !== pkg.configId && (
              <Row label="Config Name" value={configMeta.name} />
            )}
            <Row label="Config ID" value={pkg.configId} mono />
            <Row label="Config Version" value={pkg.configVersion} mono />
            <Row
              label="Created"
              value={new Date(pkg.createdAt).toLocaleString()}
            />
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
              {remediateMut.isPending ? (
                <span className="spinner" />
              ) : (
                "Run AI Remediation"
              )}
            </button>
          </div>
        </div>

        {/* Right: control panel */}
        <div>
          <PackageControlPanel pkg={pkg} />
        </div>
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-start gap-2 text-sm">
      <span className="w-32 shrink-0 text-slate-500 text-xs pt-0.5">{label}</span>
      <span
        className={`break-all ${mono ? "font-mono text-xs text-slate-300" : "text-slate-200"}`}
      >
        {value}
      </span>
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