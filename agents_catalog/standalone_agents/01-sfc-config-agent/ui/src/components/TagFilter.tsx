interface Props {
  allTags: string[];
  activeTags: string[];
  onToggle: (tag: string) => void;
  onClear: () => void;
  total: number;
  filtered: number;
}

export default function TagFilter({ allTags, activeTags, onToggle, onClear, total, filtered }: Props) {
  if (allTags.length === 0) return null;

  const isFiltered = activeTags.length > 0;

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="text-xs text-slate-500 shrink-0">Filter by tag:</span>
      {allTags.map((tag) => {
        const active = activeTags.includes(tag);
        return (
          <button
            key={tag}
            type="button"
            onClick={() => onToggle(tag)}
            className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium transition-all duration-100 ${
              active
                ? "bg-sky-600/80 text-sky-100 ring-1 ring-sky-400/60"
                : "bg-slate-800/60 text-slate-400 ring-1 ring-slate-700/40 hover:bg-slate-700/60 hover:text-slate-200"
            }`}
          >
            {tag}
          </button>
        );
      })}
      {isFiltered && (
        <>
          <button
            type="button"
            onClick={onClear}
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors px-1"
          >
            ✕ clear
          </button>
          <span className="text-xs text-slate-500 ml-1">
            {filtered} / {total}
          </span>
        </>
      )}
    </div>
  );
}