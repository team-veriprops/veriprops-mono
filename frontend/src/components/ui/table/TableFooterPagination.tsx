"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@3rdparty/ui/select";
import { Button } from "@3rdparty/ui/button";
import { useGlobalSettings } from "@stores/useGlobalSettings";

interface TableFooterPaginationProps {
  page: number;
  totalPages: number;
  onNextPage: () => void;
  onPreviousPage: () => void;
  onResetPage: () => void;
}

export default function TableFooterPagination({
  page,
  totalPages,
  onNextPage,
  onPreviousPage,
  onResetPage
}: TableFooterPaginationProps) {
  const { settings, setRowsPerPage } = useGlobalSettings();

  const adjustedPage = settings.firstPage === 0 ? page + 1 : page

  return (
    <div className="flex items-center justify-between p-4 border-t">
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
          <SelectTrigger className="w-[70px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {[5, 10, 20, 30, 50].map((size) => (
              <SelectItem key={size} value={size.toString()}>
                {size}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Pagination controls */}
      <div className="flex items-center space-x-2">
        <span className="text-sm">
          Page {adjustedPage} of {totalPages || 1}
        </span>
        <Button
          variant="ghost"
          size="sm"
          disabled={page <= settings.firstPage}
          onClick={onPreviousPage}
        >
          Prev
        </Button>
        <Button
          variant="ghost"
          size="sm"
          disabled={adjustedPage >= totalPages}
          onClick={onNextPage}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
