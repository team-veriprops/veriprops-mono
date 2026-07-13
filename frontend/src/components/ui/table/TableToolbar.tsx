"use client";

import { Input } from "@3rdparty/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@3rdparty/ui/select";
import { Search } from "lucide-react";
import { ReactNode, useState } from "react";
import { useDebouncedCallback } from "use-debounce";
import { useGlobalSettings } from "@stores/useGlobalSettings";
import type { TableFilter } from "./DataTable";

// Sentinel value for a filter's "no selection" option — Radix Select cannot use "".
const ALL = "__ALL__";

interface ToolbarProps {
  searchPlaceholder: string;
  onSearchQueryChange: (searchQuery: string) => void;
  /** Controlled search text — kept in the URL by the parent (useSyncedQueryState). */
  searchValue?: string;
  filters?: TableFilter[];
  onFilterChange?: (key: string, value: string) => void;
  children?: ReactNode;
}
export function TableToolbar({
  searchPlaceholder = "Search...",
  onSearchQueryChange,
  searchValue,
  filters = [],
  onFilterChange,
  children,
}: ToolbarProps) {
  const { settings } = useGlobalSettings();

  // Local mirror keeps typing responsive; emits are debounced. When the
  // URL-driven `searchValue` changes externally (reset/back), reset the mirror
  // during render (React's "adjust state on prop change" pattern) instead of in
  // an effect — no remount, so focus and cursor are preserved while typing.
  const [value, setValue] = useState(searchValue ?? "");
  const [lastSearchValue, setLastSearchValue] = useState(searchValue);
  if (searchValue !== lastSearchValue) {
    setLastSearchValue(searchValue);
    setValue(searchValue ?? "");
  }

  const emitSearch = useDebouncedCallback((searchTerm: string) => {
    onSearchQueryChange(searchTerm);
  }, settings.searchDebounceSeconds);

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
      <div className="flex flex-1 flex-wrap items-center gap-3">
        {/* Search Input */}
        <div className="relative flex-1 min-w-48 max-w-md">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="search"
            placeholder={searchPlaceholder}
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              emitSearch(e.target.value);
            }}
            className="pl-10"
            data-testid="datatable-search"
          />
        </div>

        {/* Filter dropdowns */}
        {filters.map((filter) => (
          <Select
            key={filter.key}
            value={filter.value && filter.value !== "" ? filter.value : ALL}
            onValueChange={(v) => onFilterChange?.(filter.key, v === ALL ? "" : v)}
          >
            <SelectTrigger className="w-44" data-testid={`datatable-filter-${filter.key}`}>
              <SelectValue placeholder={filter.label} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>{`All ${filter.label.toLowerCase()}`}</SelectItem>
              {filter.options.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ))}
      </div>

      {/* Buttons */}
      {children}
    </div>
  );
}
