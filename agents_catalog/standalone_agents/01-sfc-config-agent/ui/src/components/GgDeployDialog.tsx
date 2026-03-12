/**
 * GgDeployDialog — reusable modal for the "Create Greengrass Component" action.
 *
 * Flow:
 *   1. Confirm screen  — describes what will happen, Confirm / Cancel buttons
 *   2. Success screen  — shows the registered component ARN, Close button
 *   3. Error screen    — shows the error message, Close button
 *
 * Usage:
 *   <GgDeployDialog packageId={id} onClose={() => setOpen(false)} />
 */
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createGgComponent } from "../api/client";

interface Props {
  packageId: string;
  onClose: () => void;
}

type Phase = "confirm" | "success" | "error";

export default function GgDeployDialog({ packageId, onClose }: Props) {
  const qc = useQueryClient();
  const [phase, setPhase] = useState<Phase>("confirm");
  const [resultArn, setResultArn] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const ggMut = useMutation({
    mutationFn: () => createGgComponent(packageId),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["package", packageId] });
      qc.invalidateQueries({ queryKey: ["packages"] });
      setResultArn(data.ggComponentArn ?? null);
      setPhase("success");
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        (err instanceof Error ? err.message : String(err));
      setErrorMsg(msg);
      setPhase("error");
    },
  });

  // ── Shared overlay wrapper ───────────────────────────────────────────────
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-700/60 rounded-xl shadow-2xl w-full max-w-lg">

        {/* ── CONFIRM phase ─────────────────────────────────────────────── */}
        {phase === "confirm" && (
          <>
            <div className="px-6 pt-6 pb-4">
              <h2 className="text-sm font-semibold text-slate-100 mb-3">
                Deploy to AWS IoT Greengrass v2
              </h2>
              <p className="text-xs text-slate-400 leading-relaxed whitespace-pre-line">
                {`Publishes the S3 launch bundle as a new AWS IoT Greengrass v2 component version.\n\nComponent name:  com.sfc.<configId>  (stable across calls)\nComponent version:  YYYY.MM.DD.HHmmss  (UTC timestamp, unique per call)\n\nEach call adds a new version — previous versions are not deleted or overwritten.\nThe resulting ARN can be used in a Greengrass deployment to push SFC to edge devices managed by the local Greengrass nucleus.\n\nNote: the call is blocked if ERROR-severity SFC logs exist within the last 10 minutes.\nNo edge devices are modified by this step.`}
              </p>
            </div>
            <div className="flex justify-end gap-2 px-6 pb-5 pt-2 border-t border-slate-800">
              <button
                className="btn btn-ghost text-xs"
                onClick={onClose}
                disabled={ggMut.isPending}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary text-xs"
                onClick={() => ggMut.mutate()}
                disabled={ggMut.isPending}
              >
                {ggMut.isPending ? (
                  <span className="flex items-center gap-2">
                    <span className="spinner w-3 h-3" />
                    Registering…
                  </span>
                ) : (
                  "Create Greengrass Component"
                )}
              </button>
            </div>
          </>
        )}

        {/* ── SUCCESS phase ─────────────────────────────────────────────── */}
        {phase === "success" && (
          <>
            <div className="px-6 pt-6 pb-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-emerald-400 text-lg">✓</span>
                <h2 className="text-sm font-semibold text-emerald-300">
                  Greengrass component registered
                </h2>
              </div>
              <p className="text-xs text-slate-400 mb-3">
                The component version was successfully created in AWS IoT Greengrass v2.
                You can now use this ARN to target a Greengrass deployment.
              </p>
              {resultArn && (
                <div className="rounded-md bg-slate-800/60 border border-slate-700/50 px-3 py-2">
                  <p className="text-[10px] text-slate-500 mb-1">Component ARN</p>
                  <p className="font-mono text-xs text-emerald-300 break-all">{resultArn}</p>
                </div>
              )}
            </div>
            <div className="flex justify-end px-6 pb-5 pt-2 border-t border-slate-800">
              <button className="btn btn-primary text-xs" onClick={onClose}>
                Close
              </button>
            </div>
          </>
        )}

        {/* ── ERROR phase ───────────────────────────────────────────────── */}
        {phase === "error" && (
          <>
            <div className="px-6 pt-6 pb-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-red-400 text-lg">✕</span>
                <h2 className="text-sm font-semibold text-red-300">
                  Greengrass registration failed
                </h2>
              </div>
              <p className="text-xs text-slate-400 mb-3">
                The API call did not succeed. Check the error details below and verify the package
                status and recent SFC logs (no ERROR-severity entries in the last 10 minutes are
                allowed).
              </p>
              {errorMsg && (
                <div className="rounded-md bg-red-950/30 border border-red-800/50 px-3 py-2">
                  <p className="text-[10px] text-slate-500 mb-1">Error</p>
                  <p className="font-mono text-xs text-red-300 break-all">{errorMsg}</p>
                </div>
              )}
            </div>
            <div className="flex justify-end px-6 pb-5 pt-2 border-t border-slate-800">
              <button className="btn btn-ghost text-xs" onClick={onClose}>
                Close
              </button>
            </div>
          </>
        )}

      </div>
    </div>
  );
}
