import { useState, useMemo, SetStateAction, ReactNode } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@3rdparty/ui/table";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Checkbox } from "@3rdparty/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@3rdparty/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@3rdparty/ui/dropdown-menu";
import {
  Search,
  ChevronUp,
  ChevronDown,
  MoreHorizontal,
  Download,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Loader2,
} from "lucide-react";
import { Page, PageRequest } from "@/types/models";
import TableFooterPagination from "./TableFooterPagination";
import { useGlobalSettings } from "@stores/useGlobalSettings";
import { Card, CardContent } from "@components/3rdparty/ui/card";
import { TableToolbar } from "./TableToolbar";
import { AnimatedTableRow } from "./AnimatedTableRow";

export interface Column<T> {
  key: keyof T | string;
  label: string;
  sortable?: boolean;
  filterable?: boolean;
  render?: (value: any, item: T) => React.ReactNode;
  width?: string;
}

export interface Action<T> {
  label: string;
  shown?: (item: T) => boolean;
  onClick: (item: T) => void;
  variant?: "default" | "destructive";
  icon?: React.ComponentType<{ className?: string }>;
}

interface DataTableProps<T> {
  dataPage: Page<T>;
  columns: Column<T>[];
  actions?: Action<T>[];
  searchPlaceholder?: string;
  onSelectionChange?: (selectedItems: T[]) => void;
  bulkActions?: Action<T[]>[];
  filters?: {
    key: keyof T;
    label: string;
    options: { label: string; value: string }[];
  }[];
  className?: string;
  currentPage: number;
  updateFilters: (updates: Partial<PageRequest>) => void;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  children?: ReactNode;
  isRowClickable?: boolean;
  onRowClick?: (row: T) => void
  elementOfInterestId?: string;
}

export function DataTable<T extends Record<string, any>>({
  dataPage,
  columns,
  actions = [],
  searchPlaceholder = "Search...",
  onSelectionChange,
  bulkActions = [],
  filters = [],
  className,
  currentPage,
  updateFilters,
  isLoading,
  isError,
  error,
  children,
  isRowClickable,
  onRowClick,
  elementOfInterestId
}: DataTableProps<T>) {
  const { settings } = useGlobalSettings();
  const [orderBy, setOrderBy] = useState<string>();

  const SortIcon = ({
    columnKey,
    orderBy,
  }: {
    columnKey: any;
    orderBy?: string;
  }) => {
    if (!orderBy) return <ArrowUpDown size={14} />;
    const [sortKey, sortOrder] = orderBy.split(" ");
    if (sortKey !== columnKey) return <ArrowUpDown size={14} />;
    return sortOrder === "asc" ? (
      <ArrowUp size={14} />
    ) : (
      <ArrowDown size={14} />
    );
  };

  const handleToggleSort = (key: any) => {
    let newOrderBy: string;

    if (orderBy) {
      const [sortKey, currentOrder = "asc"] = orderBy.split(" ");

      if (sortKey === key) {
        const nextOrder = currentOrder === "asc" ? "desc" : "asc";
        newOrderBy = `${sortKey} ${nextOrder}`;
      } else {
        newOrderBy = `${key} asc`;
      }
    } else {
      newOrderBy = `${key} asc`;
    }

    setOrderBy(newOrderBy);
    updateFilters({ orderBy: newOrderBy, page: settings.firstPage });
  };

  const handleNextPage = () => {
    if (dataPage?.nextPage) {
      updateFilters({ page: dataPage?.nextPage });
    }
  };

  const handlePrevPage = () => {
    if (dataPage?.prevPage !== undefined && dataPage?.prevPage >= 0) {
      updateFilters({ page: dataPage?.prevPage });
    }
  };

  const handlePageReset = () => {
    updateFilters({ page: settings.firstPage });
  };

  const onSearchQueryChange = (searchQuery: string) => {
    updateFilters({ query: searchQuery, page: settings.firstPage });
  };

  return (
    <Card className="border-border">
      <CardContent className="p-6">
        {/* Toolbar */}
        <TableToolbar
          onSearchQueryChange={onSearchQueryChange}
          searchPlaceholder={searchPlaceholder}
        >
          {children}
        </TableToolbar>
        <Table>
          <TableHeader className="bg-muted/50 border-b">
            <TableRow>
              {/* {(onSelectionChange || bulkActions.length > 0) && (
                <TableHead className="w-12">
                  <Checkbox
                    checked={selectedItems.length === paginatedData.length && paginatedData.length > 0}
                    onCheckedChange={handleSelectAll}
                  />
                </TableHead>
              )} */}
              {columns.map((column) => (
                <TableHead
                  key={String(column.key)}
                  className={`px-6 py-4 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider
                    ${column.sortable ? "cursor-pointer hover:bg-accent" : ""}
                    `
                  }
                  style={{ width: column.width }}
                  onClick={() => handleToggleSort(column.key)}
                >
                  <div className="flex items-center gap-1">
                    {column.label}
                    <SortIcon columnKey={column.key} orderBy={orderBy} />
                  </div>
                </TableHead>
              ))}
              {actions.length > 0 && (
                <TableHead className="w-20 px-6 py-4 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Actions</TableHead>
              )}
            </TableRow>
          </TableHeader>
          <TableBody className="divide-y divide-border bg-card">
            {isLoading ? (
              <TableRow>
                <TableCell
                  colSpan={
                    columns.length +
                    (actions.length > 0 ? 1 : 0) +
                    (onSelectionChange ? 1 : 0)
                  }
                  className="flex items-center justify-center py-8 text-muted-foreground"
                >
                  <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                  Fetching data...
                </TableCell>
              </TableRow>
            ) : isError ? (
              <TableRow>
                <TableCell
                  colSpan={
                    columns.length +
                    (actions.length > 0 ? 1 : 0) +
                    (onSelectionChange ? 1 : 0)
                  }
                  className="text-center py-8 text-destructive"
                >
                  Something went wrong. Please try again.
                </TableCell>
              </TableRow>
            ) : !dataPage || dataPage.items.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={
                    columns.length +
                    (actions.length > 0 ? 1 : 0) +
                    (onSelectionChange ? 1 : 0)
                  }
                  className="text-center py-8 text-muted-foreground"
                >
                  No data found
                </TableCell>
              </TableRow>
            ) : (
              dataPage.items.map((item, index) => (
                <AnimatedTableRow
                  key={item.id}
                  id={item.id!}
                  index={index}
                  isClickable={isRowClickable}
                  onClick={() => onRowClick && onRowClick(item)}
                  elementOfInterest={elementOfInterestId}
                >
                  {/* {(onSelectionChange || bulkActions.length > 0) && (
                  <TableCell>
                    <Checkbox
                      checked={selectedItems.includes(item)}
                      onCheckedChange={(checked: boolean) =>
                        handleSelectItem(item, checked as boolean)
                      }
                    />
                  </TableCell>
                )} */}
                  {columns.map((column) => (
                    <TableCell key={String(column.key)}>
                      {column.render
                        ? column.render(item[column.key as keyof T], item)
                        : String(item[column.key as keyof T] || "")}
                    </TableCell>
                  ))}
                  {actions.length > 0 && (
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          {actions
                            .filter((action) => action.shown?.(item) ?? true)
                            .map((action, actionIndex) => (
                              <DropdownMenuItem
                                key={actionIndex}
                                onClick={() => action.onClick(item)}
                                className={
                                  action.variant === "destructive"
                                    ? "text-destructive"
                                    : ""
                                }
                              >
                                {action.icon && (
                                  <action.icon className="h-4 w-4 mr-2" />
                                )}
                                {action.label}
                              </DropdownMenuItem>
                            ))}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  )}
                </AnimatedTableRow>
              ))
            )}
          </TableBody>
        </Table>

        {/* Pagination footer */}
        <TableFooterPagination
          page={currentPage}
          totalPages={dataPage?.totalPages || 0}
          onPreviousPage={handlePrevPage}
          onNextPage={handleNextPage}
          onResetPage={handlePageReset}
        />
      </CardContent>
    </Card>
  );
}
