import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getPackage, triggerRemediation, pollRemediation } from "../api/client";
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

  // Phase 1: trigger → store sessionId
  const [pendingSessionId, setPendingSessionId] = useState<string | null>(null);
  const [remediationResult, setRemediationResult] = useState<string | null>(null);
  const [remediationError, setRemediationError] = useState<string | null>(null);

  const triggerMut = useMutation({
    mutationFn: ({ selectedErrors, start, end }: { selectedErrors: string[]; start: string; end: string }) =>
      triggerRemediation(packageId!, start, end, selectedErrors),
    onSuccess: (res) => {
      setPendingSessionId(res.sessionId);
      setRemediationResult(null);
      setRemediationError(null);
    },
    onError: () => {
      setRemediationError("Failed to start AI remediation.");
    },
  });

  // Phase 2: poll until COMPLETE or FAILED
  const { data: pollData } = useQuery({
    queryKey: ["remediation", packageId, pendingSessionId],
    queryFn: () => pollRemediation(packageId!, pendingSessionId!),
    enabled: !!pendingSessionId,
    refetchInterval: (data) =>
      data.state.data?.status === "PENDING" ? 4000 : false,
  });

  useEffect(() => {
    if (!pollData) return;
    if (pollData.status === "COMPLETE") {
      qc.invalidateQueries({ queryKey: ["package", packageId] });
      setRemediationResult(
        `Remediation complete. New config version: ${pollData.newConfigVersion}`
      );
      setPendingSessionId(null);
    } else if (pollData.status === "FAILED") {
      setRemediationError(pollData.error ?? "AI remediation failed.");
      setPendingSessionId(null);
    }
  }, [pollData, packageId, qc]);

  const isPending = !!pendingSessionId || triggerMut.isPending;

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

      {/* Remediation status banners */}
      {isPending && (
        <div className="shrink-0 flex items-center gap-2 px-3 py-2 rounded bg-sky-950/40 border border-sky-800/50">
          <span className="spinner w-3.5 h-3.5 border-sky-400" />
          <p className="text-xs text-sky-300">
            AI is analysing errors
            {pollData?.status === "PENDING" ? " — Bedrock AgentCore Runtime is processing…" : "…"}
          </p>
        </div>
      )}
      {remediationResult && (
        <div className="shrink-0 flex items-center gap-2 px-3 py-2 rounded bg-green-950/40 border border-green-800/50">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-green-400 shrink-0">
            <path fillRule="evenodd" d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm3.857-9.809a.75.75 0 0 0-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 1 0-1.06 1.061l2.5 2.5a.75.75 0 0 0 1.137-.089l4-5.5Z" clipRule="evenodd" />
          </svg>
          <p className="text-xs text-green-300">{remediationResult}</p>
          <button className="ml-auto text-xs text-slate-500 hover:text-slate-300" onClick={() => setRemediationResult(null)}>✕</button>
        </div>
      )}
      {remediationError && (
        <div className="shrink-0 flex items-center gap-2 px-3 py-2 rounded bg-red-950/40 border border-red-800/50">
          <p className="text-xs text-red-300">{remediationError}</p>
          <button className="ml-auto text-xs text-slate-500 hover:text-slate-300" onClick={() => setRemediationError(null)}>✕</button>
        </div>
      )}

      {/* Log stream */}
      <div className="flex-1 min-h-0">
        {packageId && (
          <OtelLogStream
            packageId={packageId}
            onFixWithAI={(selectedErrors, start, end) => {
              if (!isPending) triggerMut.mutate({ selectedErrors, start, end });
            }}
          />
        )}
      </div>
    </div>
  );
}
