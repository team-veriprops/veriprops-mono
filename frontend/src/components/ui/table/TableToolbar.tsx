"use client";

import { Input } from "@3rdparty/ui/input";
import { Search } from "lucide-react";
import { ReactNode } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useDebouncedCallback } from "use-debounce";
import { useGlobalSettings } from "@stores/useGlobalSettings";

interface ToolbarProps {
  searchPlaceholder: string;
  onSearchQueryChange: (searchQuery: string) => void;
  children?: ReactNode;
}
export function TableToolbar({
  searchPlaceholder = "Search...",
  onSearchQueryChange,
  children,
}: ToolbarProps) {
  const { settings } = useGlobalSettings();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { replace } = useRouter();

  const handleSearchTextChange = useDebouncedCallback((searchTerm) => {
    console.log(`Searching... ${searchTerm}`);
    onSearchQueryChange(searchTerm);
  }, settings.searchDebounceSeconds);

  return (
    <div className="flex items-center justify-between gap-4 mb-6">
      {/* Search Input */}
      <div className="relative flex-1 max-w-md">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          type="search"
          placeholder={searchPlaceholder}
          defaultValue={searchParams.get("query")?.toString()}
          onChange={(e) => handleSearchTextChange(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Buttons */}
      {children}
    </div>
  );
}
