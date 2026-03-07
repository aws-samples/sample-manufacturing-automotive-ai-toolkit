import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getHeartbeat, type HeartbeatStatus } from "../api/client";

interface Props {
  packageId: string;
  compact?: boolean; // true → inline LED only (for table rows)
}

function ledClass(status: HeartbeatStatus["liveStatus"]) {
  if (status === "ACTIVE") return "bg-green-400";
  if (status === "ERROR") return "bg-red-400";
  return "bg-slate-500";
}

function ledLabel(status: HeartbeatStatus["liveStatus"]) {
  if (status === "ACTIVE") return "ACTIVE";
  if (status === "ERROR") return "ERROR";
  return "INACTIVE";
}

function relativeTime(iso?: string) {
  if (!iso) return "never";
  const diff = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  return `${Math.round(diff / 3600)}h ago`;
}

/** Ticks every second so that "Last seen" counts up in real time. */
function useTick(intervalMs = 1_000) {
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
}

export default function HeartbeatStatusLed({ packageId, compact }: Props) {
  const { data } = useQuery({
    queryKey: ["heartbeat", packageId],
    queryFn: () => getHeartbeat(packageId),
    refetchInterval: 10_000,
    staleTime: 8_000,
  });

  // Re-render every second so the relative timestamp counts up live
  useTick();

  const status = data?.liveStatus ?? "INACTIVE";

  if (compact) {
    return (
      <span className="flex items-center gap-1.5">
        <span
          className={`inline-block w-2 h-2 rounded-full ${ledClass(status)} ${
            status === "ACTIVE" ? "animate-pulse" : ""
          }`}
        />
        <span
          className={`text-xs ${
            status === "ACTIVE"
              ? "text-green-400"
              : status === "ERROR"
              ? "text-red-400"
              : "text-slate-500"
          }`}
        >
          {ledLabel(status)}
        </span>
        {data?.lastHeartbeatAt && (
          <span className="text-xs text-slate-600">
            {relativeTime(data.lastHeartbeatAt)}
          </span>
        )}
      </span>
    );
  }

  // Full card variant for PackageDetail
  return (
    <div className="card mb-4">
      <div className="flex items-center gap-2 mb-3">
        <span
          className={`w-3 h-3 rounded-full ${ledClass(status)} ${
            status === "ACTIVE" ? "animate-pulse" : ""
          }`}
        />
        <span
          className={`font-semibold text-sm ${
            status === "ACTIVE"
              ? "text-green-400"
              : status === "ERROR"
              ? "text-red-400"
              : "text-slate-400"
          }`}
        >
          {ledLabel(status)}
        </span>
        <span className="text-slate-600 text-xs">—</span>
        <span className="text-xs text-slate-400">
          {data?.sfcRunning ? "SFC running" : "SFC stopped"}
        </span>
        {data?.lastHeartbeatAt && (
          <>
            <span className="text-slate-600 text-xs">—</span>
            <span className="text-xs text-slate-500">
              Last seen: {relativeTime(data.lastHeartbeatAt)}
            </span>
          </>
        )}
      </div>

      {data && data.recentLogs.length > 0 && (
        <>
          <p className="text-xs text-slate-500 mb-1 font-medium">
            Recent SFC output:
          </p>
          <div className="bg-[#0f1117] rounded p-2 font-mono text-xs space-y-0.5 max-h-24 overflow-y-auto">
            {data.recentLogs.map((line, i) => {
              const upper = line.toUpperCase();
              const cls = upper.includes("ERROR")
                ? "log-error"
                : upper.includes("WARN")
                ? "log-warn"
                : "log-info";
              return (
                <div key={i} className={cls}>
                  {line}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}