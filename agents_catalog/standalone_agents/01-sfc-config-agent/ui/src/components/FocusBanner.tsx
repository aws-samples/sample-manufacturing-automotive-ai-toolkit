import { useQuery } from "@tanstack/react-query";
import { getFocus } from "../api/client";

export default function FocusBanner() {
  const { data } = useQuery({
    queryKey: ["focus"],
    queryFn: getFocus,
    staleTime: 30_000,
  });

  if (!data?.focusedConfigId) return null;

  return (
    <div className="bg-sky-950/60 border-b border-sky-800/50 px-4 py-1.5 flex items-center gap-3 text-xs text-sky-300">
      <span className="font-mono text-sky-500">FOCUS</span>
      <span className="font-medium">{data.focusedConfigId}</span>
      <span className="text-sky-600">@</span>
      <span className="font-mono text-sky-400 truncate max-w-xs">
        {data.focusedConfigVersion}
      </span>
    </div>
  );
}