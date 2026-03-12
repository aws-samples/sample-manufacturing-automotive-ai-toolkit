import { useState, useRef, KeyboardEvent } from "react";

interface Props {
  tags: string[];
  onChange: (tags: string[]) => void;
  disabled?: boolean;
  placeholder?: string;
}

export default function TagEditor({ tags, onChange, disabled = false, placeholder = "Add tag…" }: Props) {
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  function addTag(raw: string) {
    const value = raw.trim().toLowerCase().replace(/\s+/g, "-");
    if (!value || tags.includes(value)) {
      setInput("");
      return;
    }
    onChange([...tags, value]);
    setInput("");
  }

  function removeTag(tag: string) {
    onChange(tags.filter((t) => t !== tag));
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTag(input);
    } else if (e.key === "Backspace" && input === "" && tags.length > 0) {
      removeTag(tags[tags.length - 1]);
    }
  }

  return (
    <div
      className="flex flex-wrap items-center gap-1.5 min-h-[32px] px-2 py-1 rounded-md border border-[#252d3d] bg-[#0d1117] cursor-text focus-within:border-sky-700/60 transition-colors"
      onClick={() => inputRef.current?.focus()}
    >
      {tags.map((tag) => (
        <span
          key={tag}
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-sky-900/40 text-sky-300 text-xs font-medium ring-1 ring-sky-700/40"
        >
          {tag}
          {!disabled && (
            <button
              type="button"
              className="text-sky-400/60 hover:text-sky-200 leading-none"
              onClick={(e) => { e.stopPropagation(); removeTag(tag); }}
              tabIndex={-1}
            >
              ×
            </button>
          )}
        </span>
      ))}
      {!disabled && (
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => { if (input.trim()) addTag(input); }}
          placeholder={tags.length === 0 ? placeholder : ""}
          className="flex-1 min-w-[80px] bg-transparent text-xs text-slate-300 placeholder-slate-600 outline-none"
        />
      )}
    </div>
  );
}