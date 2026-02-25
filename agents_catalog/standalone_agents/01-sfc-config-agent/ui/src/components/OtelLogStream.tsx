import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getLogs, type LogEvent } from "../api/client";

interface Props {
  packageId: string;
  errorsOnly?: boolean;
  onFixWithAI?: (start: string, end: string) => void;
}

function logClass(msg: string) {
  const u = msg.toUpperCase();
  if (u.includes("ERROR")) return "log-error";
  if (u.includes("WARN")) return "log-warn";
  if (u.includes("DEBUG")) return "log-debug";
  return "log-info";
}

function fmtTs(ts: number) {
  return new Date(ts).toISOString().replace("T", " ").slice(0, 23);
}

export default function OtelLogStream({
  packageId,
  errorsOnly = false,
  onFixWithAI,
}: Props) {
  const [nextToken, setNextToken] = useState<string | undefined>();

  const { data, isFetching, refetch } = useQuery({
    queryKey: ["logs", packageId, errorsOnly, nextToken],
    queryFn: () =>
      getLogs(packageId, { limit: 100, errorsOnly, nextToken }),
    staleTime: 15_000,
  });

  const events: LogEvent[] = data?.events ?? [];
  const hasErrors = events.some((e) => e.message.toUpperCase().includes("ERROR"));

  function handleFixWithAI() {
    if (!onFixWithAI || events.length === 0) return;
    const sorted = [...events].sort((a, b) => a.timestamp - b.timestamp);
    const start = new Date(sorted[0].timestamp).toISOString();
    const end = new Date(sorted[sorted.length - 1].timestamp).toISOString();
    onFixWithAI(start, end);
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 mb-3">
        <span className="text-sm text-slate-400">
          {events.length} event{events.length !== 1 ? "s" : ""}
        </span>
        <button
          className="btn btn-secondary text-xs"
          onClick={() => { setNextToken(undefined); refetch(); }}
          disabled={isFetching}
        >
          {isFetching ? <span className="spinner" /> : "Refresh"}
        </button>
        {hasErrors && onFixWithAI && (
          <button
            className="btn btn-primary text-xs ml-auto"
            onClick={handleFixWithAI}
          >
            Fix with AI
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto bg-[#0a0c14] rounded border border-[#2a3044] p-3 font-mono text-xs space-y-0.5">
        {events.length === 0 && !isFetching && (
          <p className="text-slate-600 italic">No log events found.</p>
        )}
        {events.map((e, i) => (
          <div key={i} className={`flex gap-3 ${logClass(e.message)}`}>
            <span className="text-slate-600 shrink-0">{fmtTs(e.timestamp)}</span>
            <span className="break-all">{e.message}</span>
          </div>
        ))}
        {isFetching && (
          <p className="text-slate-600 italic">Loading…</p>
        )}
      </div>

      {data?.nextToken && (
        <button
          className="btn btn-ghost text-xs mt-2 self-center"
          onClick={() => setNextToken(data.nextToken)}
          disabled={isFetching}
        >
          Load more
        </button>
      )}
    </div>
  );
}