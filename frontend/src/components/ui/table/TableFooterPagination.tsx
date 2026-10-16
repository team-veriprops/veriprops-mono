"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@3rdparty/ui/select";
import ListPager from "@components/ui/ListPager";
import { useGlobalSettings } from "@stores/useGlobalSettings";
import { DATATABLE_PAGER_PREFIX, ROWS_PER_PAGE_OPTIONS } from "./testIds";

interface TableFooterPaginationProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onResetPage: () => void;
}

/** A DataTable's footer: the rows-per-page choice every table reads, and the shared pager. */
export default function TableFooterPagination({
  page,
  totalPages,
  onPageChange,
  onResetPage
}: TableFooterPaginationProps) {
  const { settings, setRowsPerPage } = useGlobalSettings();

  return (
    <div className="flex flex-col gap-3 p-4 border-t sm:flex-row sm:items-center sm:justify-between">
      {/* Rows per page selector */}
      <div className="flex items-center space-x-2">
        <span className="text-sm">Rows per page:</span>
        <Select
          value={settings.rowsPerPage.toString()}
          onValueChange={(v) => {
            setRowsPerPage(Number(v));
            onResetPage();
          }}
        >
          {/* The visible "Rows per page:" text is a sibling, not a label, so the trigger carries
              its own name rather than being announced as an unnamed button showing a number. */}
          <SelectTrigger className="w-17.5" aria-label="Rows per page">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ROWS_PER_PAGE_OPTIONS.map((size) => (
              <SelectItem key={size} value={size.toString()}>
                {size}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <ListPager
        page={page}
        totalPages={totalPages}
        onPageChange={onPageChange}
        testIdPrefix={DATATABLE_PAGER_PREFIX}
        alwaysShow
        className="sm:justify-end"
      />
    </div>
  );
}
