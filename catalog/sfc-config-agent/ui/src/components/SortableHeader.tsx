import type { SortState } from "../hooks/useSortable";

interface Props {
  column: string;
  label: string;
  sort: SortState;
  onToggle: (column: string) => void;
  className?: string;
}

export default function SortableHeader({ column, label, sort, onToggle, className }: Props) {
  const active = sort.column === column;
  return (
    <th className={className}>
      <button
        type="button"
        className={`inline-flex items-center gap-1 group transition-colors ${
          active ? "text-sky-300" : "text-slate-400 hover:text-slate-200"
        }`}
        onClick={() => onToggle(column)}
      >
        <span>{label}</span>
        <span className="text-[10px] leading-none w-2.5 text-center">
          {active ? (sort.direction === "asc" ? "▲" : "▼") : (
            <span className="opacity-0 group-hover:opacity-40">▼</span>
          )}
        </span>
      </button>
    </th>
  );
}