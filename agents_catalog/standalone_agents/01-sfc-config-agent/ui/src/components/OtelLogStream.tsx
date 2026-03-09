import { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { getLogs, type LogEvent } from "../api/client";
import RefreshButton from "./RefreshButton";
import RemediationConfirmDialog from "./RemediationConfirmDialog";

type SfcLevel = LogEvent["severityText"];

const ALL_LEVELS: SfcLevel[] = ["TRACE", "INFO", "WARNING", "ERROR"];
const LIVE_INTERVAL_MS = 10_000;

interface Props {
  packageId: string;
  errorsOnly?: boolean;
  onFixWithAI?: (selectedErrors: string[], start: string, end: string) => void;
}

function logClass(severity: SfcLevel) {
  switch (severity) {
    case "ERROR":   return "log-error";
    case "WARNING": return "log-warn";
    case "TRACE":   return "text-slate-600";
    default:        return "log-info";
  }
}

const LEVEL_BADGE: Record<SfcLevel, string> = {
  TRACE:   "bg-slate-700 text-slate-400",
  INFO:    "bg-sky-900/60 text-sky-300",
  WARNING: "bg-yellow-900/60 text-yellow-300",
  ERROR:   "bg-red-900/60 text-red-300",
};

/** Strip ANSI/VT escape sequences from a string */
// eslint-disable-next-line no-control-regex
const ANSI_RE = /\x1B\[[0-9;]*[A-Za-z]/g;
function stripAnsi(s: string) {
  return s.replace(ANSI_RE, "");
}

export default function OtelLogStream({
  packageId,
  errorsOnly = false,
  onFixWithAI,
}: Props) {
  const [activeLevels, setActiveLevels] = useState<Set<SfcLevel>>(
    new Set(ALL_LEVELS)
  );
  const [liveMode, setLiveMode] = useState(false);
  const [dialogErrors, setDialogErrors] = useState<LogEvent[] | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  // Always fetch the latest 100 entries — no pagination token
  const { data, isFetching, refetch } = useQuery({
    queryKey: ["logs", packageId, errorsOnly, liveMode],
    queryFn: () => getLogs(packageId, { limit: 100, errorsOnly }),
    staleTime: liveMode ? 0 : 15_000,
    refetchInterval: liveMode ? LIVE_INTERVAL_MS : false,
  });

  const allRecords: LogEvent[] = data?.records ?? [];
  const records = allRecords.filter((r) => activeLevels.has(r.severityText));
  const hasVisibleErrors = allRecords.some((r) => r.severityText === "ERROR");

  // Scroll to the bottom whenever records update
  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [records]);

  function toggleLevel(level: SfcLevel) {
    setActiveLevels((prev) => {
      const next = new Set(prev);
      next.has(level) ? next.delete(level) : next.add(level);
      return next;
    });
  }

  function handleFixWithAI() {
    if (!onFixWithAI || allRecords.length === 0) return;
    const errors = allRecords.filter((r) => r.severityText === "ERROR");
    if (errors.length === 0) return;
    setDialogErrors(errors);
  }

  function handleDialogConfirm(selectedErrors: string[]) {
    if (!onFixWithAI || !dialogErrors) return;
    const sorted = [...dialogErrors].sort((a, b) =>
      a.timestamp.localeCompare(b.timestamp)
    );
    setDialogErrors(null);
    onFixWithAI(selectedErrors, sorted[0].timestamp, sorted[sorted.length - 1].timestamp);
  }

  return (
    <div className="flex flex-col h-full">
      {dialogErrors && (
        <RemediationConfirmDialog
          errors={dialogErrors}
          onConfirm={handleDialogConfirm}
          onCancel={() => setDialogErrors(null)}
        />
      )}
      {/* Toolbar */}
      <div className="flex items-center gap-3 mb-2 flex-wrap">
        <span className="text-sm text-slate-400">
          {records.length}/{allRecords.length} event
          {allRecords.length !== 1 ? "s" : ""}
        </span>

        {/* Manual refresh — hidden while live mode is active */}
        {!liveMode && (
          <RefreshButton
            onClick={() => refetch()}
            loading={isFetching}
          />
        )}

        {/* Live toggle */}
        <button
          onClick={() => setLiveMode((prev) => !prev)}
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium border transition-colors ${
            liveMode
              ? "bg-green-950/50 border-green-700/60 text-green-300"
              : "bg-transparent border-slate-700 text-slate-400 hover:text-slate-300"
          }`}
          title={liveMode ? "Stop live tail" : "Start live tail (refreshes every 10 s)"}
        >
          <span
            className={`w-2 h-2 rounded-full ${
              liveMode ? "bg-green-400 animate-pulse" : "bg-slate-600"
            }`}
          />
          Live
        </button>

        {onFixWithAI && (
          <button
            className="btn btn-primary text-xs ml-auto inline-flex items-center gap-1.5 disabled:opacity-30 disabled:cursor-not-allowed"
            onClick={handleFixWithAI}
            disabled={!hasVisibleErrors}
            title={
              hasVisibleErrors
                ? "Trigger AI remediation for visible errors"
                : "No errors detected — SFC is running well"
            }
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
            {hasVisibleErrors ? "Fix with AI" : "Running well…"}
          </button>
        )}
      </div>

      {/* Level filter toggles */}
      <div className="flex items-center gap-1.5 mb-2 flex-wrap">
        {ALL_LEVELS.map((level) => {
          const active = activeLevels.has(level);
          return (
            <button
              key={level}
              onClick={() => toggleLevel(level)}
              className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold border transition-opacity ${
                LEVEL_BADGE[level]
              } ${active ? "opacity-100 border-transparent" : "opacity-30 border-slate-600"}`}
            >
              {level}
            </button>
          );
        })}
        {activeLevels.size < ALL_LEVELS.length && (
          <button
            className="text-[10px] text-slate-500 hover:text-slate-300 ml-1"
            onClick={() => setActiveLevels(new Set(ALL_LEVELS))}
          >
            reset
          </button>
        )}
        {liveMode && isFetching && (
          <span className="text-[10px] text-green-500/70 ml-auto italic">fetching…</span>
        )}
      </div>

      {/* Log output */}
      <div className="flex-1 overflow-y-auto bg-[#0a0c14] rounded border border-[#2a3044] p-3 font-mono text-xs space-y-0.5">
        {records.length === 0 && !isFetching && (
          <p className="text-slate-600 italic">No log events found.</p>
        )}
        {records.map((r, i) => (
          <div key={i} className={logClass(r.severityText)}>
            <span className="break-all">{stripAnsi(r.body)}</span>
          </div>
        ))}
        {isFetching && (
          <p className="text-slate-600 italic">Loading…</p>
        )}
        {/* Sentinel for auto-scroll to bottom */}
        <div ref={logEndRef} />
      </div>
    </div>
  );
}
