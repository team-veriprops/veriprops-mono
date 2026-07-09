import { ReactNode, Suspense } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@3rdparty/ui/table";
import { Button } from "@3rdparty/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@3rdparty/ui/dropdown-menu";
import {
  MoreHorizontal,
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
import { AnimatedTableRow } from "../AnimatedTableRow";

export interface Column<T> {
  key: keyof T | string;
  label: string;
  sortable?: boolean;
  filterable?: boolean;
  render?: (value: unknown, item: T) => React.ReactNode;
  width?: string;
}

export interface Action<T> {
  label: string;
  shown?: (item: T) => boolean;
  onClick: (item: T) => void;
  variant?: "default" | "destructive";
  icon?: React.ComponentType<{ className?: string }>;
}

/** A single toolbar filter (rendered as a Select inside the table toolbar). */
export interface TableFilter {
  key: string;
  label: string;
  value?: string; // current selection; undefined/"" means "no filter" (ALL)
  options: { label: string; value: string }[];
}

/** Filter/search/sort/pagination intents are all emitted through one callback.
    Includes PageRequest keys (page/query/orderBy) plus any parent-defined filter keys. */
export type TableFilterUpdate = Partial<PageRequest> & Record<string, unknown>;

interface DataTableProps<T extends { id: string }> {
  dataPage: Page<T>;
  columns: Column<T>[];
  actions?: Action<T>[];
  searchPlaceholder?: string;
  /** Controlled search text (URL-synced by the parent). */
  searchValue?: string;
  /** Controlled sort, e.g. "name asc" (URL-synced by the parent). */
  orderBy?: string;
  onSelectionChange?: (selectedItems: T[]) => void;
  bulkActions?: Action<T[]>[];
  filters?: TableFilter[];
  className?: string;
  currentPage: number;
  updateFilters: (updates: TableFilterUpdate) => void;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  children?: ReactNode;
  isRowClickable?: boolean;
  onRowClick?: (row: T) => void
  elementOfInterestId?: string;
}

export function DataTable<T extends { id: string } & Record<string, unknown>>({
  dataPage,
  columns,
  actions = [],
  searchPlaceholder = "Search...",
  searchValue,
  orderBy,
  filters = [],
  onSelectionChange,
  currentPage,
  updateFilters,
  isLoading,
  isError,
  children,
  isRowClickable,
  onRowClick,
  elementOfInterestId
}: DataTableProps<T>) {
  const { settings } = useGlobalSettings();

  const SortIcon = ({
    columnKey,
    orderBy,
  }: {
    columnKey: string;
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

  const handleToggleSort = (key: string) => {
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

    updateFilters({ orderBy: newOrderBy, page: settings.firstPage });
  };

  const handleFilterChange = (key: string, value: string) => {
    updateFilters({ [key]: value, page: settings.firstPage });
  };

  const handleNextPage = () => {
    if (dataPage?.meta.nextPage) {
      updateFilters({ page: dataPage?.meta.nextPage });
    }
  };

  const handlePrevPage = () => {
    if (dataPage?.meta.prevPage !== undefined && dataPage?.meta.prevPage >= 0) {
      updateFilters({ page: dataPage?.meta.prevPage });
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
        {/* Toolbar — wrapped in Suspense because TableToolbar reads useSearchParams,
            which Next 16 requires to sit under a Suspense boundary or the page
            throws on prerender/hard navigation. */}
        <Suspense fallback={<div className="mb-6 h-10" />}>
          <TableToolbar
            onSearchQueryChange={onSearchQueryChange}
            searchPlaceholder={searchPlaceholder}
            searchValue={searchValue}
            filters={filters}
            onFilterChange={handleFilterChange}
          >
            {children}
          </TableToolbar>
        </Suspense>
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
                  onClick={() => column.sortable && handleToggleSort(String(column.key))}
                >
                  <div className="flex items-center gap-1">
                    {column.label}
                    <SortIcon columnKey={String(column.key)} orderBy={orderBy} />
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
                  id={item.id}
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
          totalPages={dataPage?.meta.totalPages || 0}
          onPreviousPage={handlePrevPage}
          onNextPage={handleNextPage}
          onResetPage={handlePageReset}
        />
      </CardContent>
    </Card>
  );
}
