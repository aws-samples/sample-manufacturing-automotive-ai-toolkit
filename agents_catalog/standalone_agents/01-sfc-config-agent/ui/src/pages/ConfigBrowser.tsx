import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { listConfigs, createConfig, getFocus } from "../api/client";
import StatusBadge from "../components/StatusBadge";
import { useState } from "react";

export default function ConfigBrowser() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: rawConfigs, isLoading } = useQuery({
    queryKey: ["configs"],
    queryFn: listConfigs,
  });
  const configs = Array.isArray(rawConfigs) ? rawConfigs : [];

  const { data: focus } = useQuery({
    queryKey: ["focus"],
    queryFn: getFocus,
    staleTime: 30_000,
  });
  const focusedConfigId = focus?.focusedConfigId;

  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");

  const createMut = useMutation({
    mutationFn: () =>
      createConfig({ name: newName, description: newDesc, content: "{}" }),
    onSuccess: (cfg) => {
      qc.invalidateQueries({ queryKey: ["configs"] });
      setShowNew(false);
      navigate(`/configs/${cfg.configId}`);
    },
  });

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-lg font-semibold">SFC Configurations</h1>
        <button className="btn btn-primary" onClick={() => setShowNew(true)}>
          + New Config
        </button>
      </div>

      {isLoading && <p className="text-slate-500 text-sm">Loading…</p>}

      {configs && configs.length === 0 && (
        <p className="text-slate-500 text-sm italic">
          No configurations yet. Create one to get started.
        </p>
      )}

      {configs && configs.length > 0 && (
        <div className="card overflow-hidden p-0">
          <table className="table-base">
            <thead>
              <tr>
                <th>Name</th>
                <th>Config ID</th>
                <th>Version</th>
                <th>Status</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {configs.map((c) => {
                const isFocused = c.configId === focusedConfigId;
                return (
                <tr
                  key={c.configId}
                  className={`cursor-pointer ${isFocused ? "bg-sky-950/40 hover:bg-sky-950/60" : ""}`}
                  onClick={() => navigate(`/configs/${c.configId}`)}
                >
                  <td className="font-medium flex items-center gap-2">
                    {c.name}
                    {isFocused && (
                      <span className="text-[10px] font-mono font-semibold bg-sky-900/60 text-sky-300 border border-sky-700 rounded px-1.5 py-0.5 leading-none">
                        FOCUS
                      </span>
                    )}
                  </td>
                  <td className="font-mono text-xs text-slate-400">{c.configId}</td>
                  <td className="font-mono text-xs text-slate-400 max-w-[200px] truncate">
                    {c.version}
                  </td>
                  <td>
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="text-xs text-slate-500">
                    {new Date(c.createdAt).toLocaleDateString()}
                  </td>
                  <td>
                    <button
                      className="btn btn-ghost text-xs"
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/configs/${c.configId}`);
                      }}
                    >
                      Edit
                    </button>
                  </td>
                </tr>
              );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* New config modal */}
      {showNew && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="card w-full max-w-md shadow-xl space-y-4">
            <h2 className="text-base font-semibold">New Configuration</h2>
            <input
              className="w-full bg-[#0f1117] border border-[#2a3044] rounded px-3 py-2 text-sm"
              placeholder="Config name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <input
              className="w-full bg-[#0f1117] border border-[#2a3044] rounded px-3 py-2 text-sm"
              placeholder="Description (optional)"
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
            />
            <div className="flex justify-end gap-2">
              <button className="btn btn-secondary" onClick={() => setShowNew(false)}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                disabled={!newName || createMut.isPending}
                onClick={() => createMut.mutate()}
              >
                {createMut.isPending ? <span className="spinner" /> : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}