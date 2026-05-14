"use client";

import { useState } from "react";
import { Eye, EyeOff, Pencil, Trash2 } from "lucide-react";
import {
  useAdminContent,
  usePublishContentItemMutation,
  useDeleteContentItemMutation,
} from "@components/admin/libs/useAdminQueries";
import type { ContentItemDto, ContentItemType } from "@components/admin/libs/admin-service";
import ContentItemForm from "./ContentItemForm";

interface ContentItemTableProps {
  itemType?: ContentItemType;
}

export default function ContentItemTable({ itemType }: ContentItemTableProps) {
  const [editingItem, setEditingItem] = useState<ContentItemDto | null>(null);
  const [page, setPage] = useState(0);

  const { data, isLoading } = useAdminContent({ itemType, page });
  const publishMutation = usePublishContentItemMutation();
  const deleteMutation = useDeleteContentItemMutation();

  const items = data?.items ?? [];
  const total = data?.meta?.total ?? 0;
  const pageCount = Math.ceil(total / 25);

  if (editingItem) {
    return (
      <ContentItemForm
        item={editingItem}
        defaultType={itemType}
        onClose={() => setEditingItem(null)}
      />
    );
  }

  return (
    <div className="space-y-4">
      {isLoading ? (
        <div className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>Loading…</div>
      ) : items.length === 0 ? (
        <div className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>No content items found.</div>
      ) : (
        <div className="overflow-x-auto rounded-xl" style={{ border: "1px solid rgba(196,198,207,0.2)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: "rgba(63,102,83,0.04)", borderBottom: "1px solid rgba(196,198,207,0.2)" }}>
                <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Title</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Type</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Status</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Sort</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item: ContentItemDto) => (
                <tr key={item.id} style={{ borderBottom: "1px solid rgba(196,198,207,0.12)" }}>
                  <td className="px-4 py-3 font-medium" style={{ color: "var(--brand-navy)" }}>
                    {item.title}
                    {item.lga && <span className="ml-2 text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>{item.state} / {item.lga}</span>}
                  </td>
                  <td className="px-4 py-3 text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>{item.itemType}</td>
                  <td className="px-4 py-3">
                    <span
                      className="px-2 py-0.5 rounded-full text-xs font-medium"
                      style={{
                        color: item.isPublished ? "#10b981" : "#f59e0b",
                        background: item.isPublished ? "#10b9811A" : "#f59e0b1A",
                      }}
                    >
                      {item.isPublished ? "Published" : "Draft"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>{item.sortOrder}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        className="p-1.5 rounded-lg"
                        style={{ color: "var(--brand-on-surface-variant)" }}
                        onClick={() => publishMutation.mutate({ itemId: item.id, isPublished: !item.isPublished })}
                        title={item.isPublished ? "Unpublish" : "Publish"}
                      >
                        {item.isPublished ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                      <button
                        type="button"
                        className="p-1.5 rounded-lg"
                        style={{ color: "var(--brand-viridian)" }}
                        onClick={() => setEditingItem(item)}
                        title="Edit"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button
                        type="button"
                        className="p-1.5 rounded-lg"
                        style={{ color: "var(--destructive)" }}
                        onClick={() => deleteMutation.mutate(item.id)}
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {pageCount > 1 && (
        <div className="flex items-center gap-2 justify-end">
          <button
            type="button"
            className="px-3 py-1 rounded-lg text-sm border disabled:opacity-40"
            style={{ borderColor: "rgba(196,198,207,0.4)" }}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
          >
            Previous
          </button>
          <span className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
            {page + 1} / {pageCount}
          </span>
          <button
            type="button"
            className="px-3 py-1 rounded-lg text-sm border disabled:opacity-40"
            style={{ borderColor: "rgba(196,198,207,0.4)" }}
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
            disabled={page >= pageCount - 1}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
