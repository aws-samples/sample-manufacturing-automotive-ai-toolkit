import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getFocus, clearFocus, listConfigs } from "../api/client";

export default function FocusBanner() {
  const qc = useQueryClient();

  const { data: focus } = useQuery({
    queryKey: ["focus"],
    queryFn: getFocus,
    staleTime: 30_000,
  });

  const { data: configs } = useQuery({
    queryKey: ["configs"],
    queryFn: listConfigs,
    staleTime: 60_000,
  });

  const clearMut = useMutation({
    mutationFn: clearFocus,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["focus"] });
    },
  });

  if (!focus?.focusedConfigId) return null;

  const configName = configs?.find((c) => c.configId === focus.focusedConfigId)?.name;

  return (
    <div className="bg-sky-950/60 border-b border-sky-800/50 px-4 py-1.5 flex items-center gap-3 text-xs text-sky-300">
      <span className="font-mono text-sky-500 shrink-0">FOCUS</span>
      {configName && (
        <span className="font-semibold text-sky-200">{configName}</span>
      )}
      <span className="font-mono text-sky-400 truncate max-w-[240px]" title={focus.focusedConfigId}>
        {focus.focusedConfigId}
      </span>
      <span className="text-sky-600">@</span>
      <span className="font-mono text-sky-500 truncate max-w-xs" title={focus.focusedConfigVersion}>
        {focus.focusedConfigVersion}
      </span>
      <button
        className="ml-auto shrink-0 text-xs text-sky-500 hover:text-red-400 border border-sky-800 hover:border-red-500 rounded px-2 py-0.5 transition-colors"
        onClick={() => clearMut.mutate()}
        disabled={clearMut.isPending}
        title="Clear focus"
      >
        {clearMut.isPending ? "…" : "Clear Focus"}
      </button>
    </div>
  );
}