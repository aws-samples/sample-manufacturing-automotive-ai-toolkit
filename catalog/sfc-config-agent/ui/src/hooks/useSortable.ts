import { useState, useMemo } from "react";

export type SortDirection = "asc" | "desc";

export interface SortState {
  column: string;
  direction: SortDirection;
}

export function useSortable<T>(
  items: T[] | undefined,
  defaultColumn: string,
  defaultDirection: SortDirection = "desc",
  getValue: (item: T, column: string) => string | number | undefined
) {
  const [sort, setSort] = useState<SortState>({
    column: defaultColumn,
    direction: defaultDirection,
  });

  function toggle(column: string) {
    setSort((prev) =>
      prev.column === column
        ? { column, direction: prev.direction === "asc" ? "desc" : "asc" }
        : { column, direction: "asc" }
    );
  }

  const sorted = useMemo(() => {
    if (!items) return [];
    return [...items].sort((a, b) => {
      const va = getValue(a, sort.column) ?? "";
      const vb = getValue(b, sort.column) ?? "";
      const cmp = va < vb ? -1 : va > vb ? 1 : 0;
      return sort.direction === "asc" ? cmp : -cmp;
    });
  }, [items, sort]);

  return { sort, toggle, sorted };
}