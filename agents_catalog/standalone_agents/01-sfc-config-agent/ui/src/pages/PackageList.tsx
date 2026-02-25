import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { listPackages, deletePackage, createGgComponent } from "../api/client";
import StatusBadge from "../components/StatusBadge";
import HeartbeatStatusLed from "../components/HeartbeatStatusLed";

export default function PackageList() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: packages, isLoading } = useQuery({
    queryKey: ["packages"],
    queryFn: listPackages,
    refetchInterval: 15_000,
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deletePackage(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["packages"] }),
  });

  const ggMut = useMutation({
    mutationFn: (id: string) => createGgComponent(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["packages"] }),
  });

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-lg font-semibold">Launch Packages</h1>
        <button
          className="btn btn-primary"
          onClick={() => navigate("/")}
        >
          + New Package (via Config)
        </button>
      </div>

      {isLoading && <p className="text-slate-500 text-sm">Loading…</p>}

      {packages && packages.length === 0 && (
        <p className="text-slate-500 text-sm italic">
          No launch packages yet. Create one from a config.
        </p>
      )}

      {packages && packages.length > 0 && (
        <div className="card overflow-hidden p-0">
          <table className="table-base">
            <thead>
              <tr>
                <th>Package ID</th>
                <th>Config</th>
                <th>Status</th>
                <th>Live</th>
                <th>Last Seen</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {packages.map((pkg) => (
                <tr
                  key={pkg.packageId}
                  className="cursor-pointer"
                  onClick={() => navigate(`/packages/${pkg.packageId}`)}
                >
                  <td className="font-mono text-xs text-slate-300">
                    {pkg.packageId}
                  </td>
                  <td>
                    <div className="text-sm">{pkg.configId}</div>
                    <div className="text-xs text-slate-500 font-mono truncate max-w-[160px]">
                      {pkg.configVersion}
                    </div>
                  </td>
                  <td>
                    <StatusBadge status={pkg.status} />
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <HeartbeatStatusLed packageId={pkg.packageId} compact />
                  </td>
                  <td className="text-xs text-slate-500">
                    {pkg.lastHeartbeatAt
                      ? new Date(pkg.lastHeartbeatAt).toLocaleTimeString()
                      : "—"}
                  </td>
                  <td className="text-xs text-slate-500">
                    {new Date(pkg.createdAt).toLocaleDateString()}
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center gap-1">
                      <button
                        className="btn btn-ghost text-xs"
                        onClick={() =>
                          navigate(`/packages/${pkg.packageId}/logs`)
                        }
                      >
                        Logs
                      </button>
                      <button
                        className="btn btn-ghost text-xs"
                        disabled={
                          pkg.status !== "READY" || ggMut.isPending
                        }
                        onClick={() => ggMut.mutate(pkg.packageId)}
                        title="Create Greengrass v2 component"
                      >
                        GG
                      </button>
                      <button
                        className="btn btn-ghost text-xs text-red-500 hover:text-red-400"
                        onClick={() => {
                          if (
                            confirm(
                              `Delete package ${pkg.packageId}?`
                            )
                          )
                            deleteMut.mutate(pkg.packageId);
                        }}
                      >
                        Del
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}