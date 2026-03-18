import { useState } from "react";
import type { LogEvent } from "../api/client";

// eslint-disable-next-line no-control-regex
const ANSI_RE = /\x1B\[[0-9;]*[A-Za-z]/g;
function stripAnsi(s: string) {
  return s.replace(ANSI_RE, "");
}

interface Props {
  errors: LogEvent[];
  onConfirm: (selectedErrors: string[]) => void;
  onCancel: () => void;
}

export default function RemediationConfirmDialog({ errors, onConfirm, onCancel }: Props) {
  const [selected, setSelected] = useState<Set<number>>(() => new Set(errors.map((_, i) => i)));

  function toggle(idx: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(idx) ? next.delete(idx) : next.add(idx);
      return next;
    });
  }

  function selectAll() {
    setSelected(new Set(errors.map((_, i) => i)));
  }

  function deselectAll() {
    setSelected(new Set());
  }

  function handleConfirm() {
    const msgs = errors
      .filter((_, i) => selected.has(i))
      .map((e) => stripAnsi(e.body));
    onConfirm(msgs);
  }

  function formatTs(ts: string) {
    try {
      return new Date(ts).toISOString().replace("T", " ").slice(0, 23) + "Z";
    } catch {
      return ts;
    }
  }

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}
    >
      <div className="w-full max-w-2xl mx-4 rounded-lg border border-slate-700 bg-[#0f1117] shadow-2xl flex flex-col max-h-[80vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700 shrink-0">
          <div className="flex items-center gap-2">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="w-4 h-4 text-violet-400 shrink-0"
            >
              <polyline points="2,20 9,7 13,13 16,9 22,20" />
              <polyline points="14.3,11 16,9 17.7,11.4" />
            </svg>
            <h2 className="text-sm font-semibold text-slate-100">Fix with AI — select errors to send</h2>
          </div>
          <button
            className="text-slate-500 hover:text-slate-300 text-base leading-none"
            onClick={onCancel}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Subtitle */}
        <p className="px-5 pt-3 pb-1 text-xs text-slate-400 shrink-0">
          The following <span className="text-red-400 font-semibold">ERROR</span> entries are currently loaded in the log viewer.
          Select the ones you want the AI agent to analyse and remediate.
        </p>

        {/* Error list */}
        <div className="flex-1 overflow-y-auto px-5 py-2 space-y-1.5">
          {errors.map((e, i) => {
            const checked = selected.has(i);
            return (
              <label
                key={i}
                className={`flex items-start gap-3 px-3 py-2 rounded cursor-pointer border transition-colors ${
                  checked
                    ? "bg-red-950/30 border-red-800/40"
                    : "bg-transparent border-slate-800/60 opacity-50"
                }`}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggle(i)}
                  className="mt-0.5 shrink-0 accent-red-500"
                />
                <div className="min-w-0">
                  <span className="block font-mono text-[10px] text-slate-500 mb-0.5">
                    {formatTs(e.timestamp)}
                  </span>
                  <span className="block font-mono text-xs text-red-300 break-all">
                    {stripAnsi(e.body)}
                  </span>
                </div>
              </label>
            );
          })}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-slate-700 shrink-0 gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <button
              className="text-xs text-slate-400 hover:text-slate-200 underline underline-offset-2"
              onClick={selectAll}
            >
              Select all
            </button>
            <button
              className="text-xs text-slate-400 hover:text-slate-200 underline underline-offset-2"
              onClick={deselectAll}
            >
              Deselect all
            </button>
            <span className="text-xs text-slate-500">
              {selected.size}/{errors.length} selected
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              className="btn btn-ghost text-xs"
              onClick={onCancel}
            >
              Cancel
            </button>
            <button
              className="btn btn-primary text-xs disabled:opacity-30 disabled:cursor-not-allowed inline-flex items-center gap-1.5"
              disabled={selected.size === 0}
              onClick={handleConfirm}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="w-3.5 h-3.5 shrink-0"
              >
                <polyline points="20 6 9 17 4 12" />
              </svg>
              Confirm &amp; Remediate
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
