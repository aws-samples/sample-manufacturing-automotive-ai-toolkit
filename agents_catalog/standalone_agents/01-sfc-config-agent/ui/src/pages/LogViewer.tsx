import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getPackage, triggerRemediation } from "../api/client";
import OtelLogStream from "../components/OtelLogStream";

export default function LogViewer() {
  const { packageId } = useParams<{ packageId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: pkg } = useQuery({
    queryKey: ["package", packageId],
    queryFn: () => getPackage(packageId!),
    enabled: !!packageId,
  });

  const [remediationResult, setRemediationResult] = useState<string | null>(null);

  const remediateMut = useMutation({
    mutationFn: ({ start, end }: { start: string; end: string }) =>
      triggerRemediation(packageId!, start, end),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["package", packageId] });
      setRemediationResult(
        `Remediation complete. New config version: ${res.newConfigVersion}`
      );
    },
  });

  return (
    <div className="p-6 max-w-7xl mx-auto flex flex-col gap-4 h-[calc(100vh-7rem)]">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap shrink-0">
        <button
          className="btn btn-ghost text-xs"
          onClick={() => navigate(`/packages/${packageId}`)}
        >
          ← Package
        </button>
        <div>
          <h1 className="text-base font-semibold">Logs</h1>
          {pkg?.logGroupName && (
            <p className="text-xs text-slate-500 font-mono">{pkg.logGroupName}</p>
          )}
        </div>

      </div>

      {remediationResult && (
        <p className="text-xs text-green-400 shrink-0">{remediationResult}</p>
      )}
      {remediateMut.isError && (
        <p className="text-xs text-red-400 shrink-0">Remediation failed.</p>
      )}

      {/* Log stream */}
      <div className="flex-1 min-h-0">
        {packageId && (
          <OtelLogStream
            packageId={packageId}
            onFixWithAI={(start, end) => remediateMut.mutate({ start, end })}
          />
        )}
      </div>
    </div>
  );
}