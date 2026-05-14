"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  useCreateContentItemMutation,
  useUpdateContentItemMutation,
} from "@components/admin/libs/useAdminQueries";
import type { ContentItemDto, ContentItemType } from "@components/admin/libs/admin-service";
import { getErrorMessage } from "@lib/utils";

const CONTENT_TYPES: { value: ContentItemType; label: string }[] = [
  { value: "HOW_IT_WORKS_STEP", label: "How It Works Step" },
  { value: "FAQ", label: "FAQ" },
  { value: "TESTIMONIAL", label: "Testimonial" },
  { value: "AGENT_SPOTLIGHT", label: "Agent Spotlight" },
  { value: "AREA_INSIGHT", label: "Area Insight" },
];

const schema = z.object({
  itemType: z.enum(["HOW_IT_WORKS_STEP", "FAQ", "TESTIMONIAL", "AGENT_SPOTLIGHT", "AREA_INSIGHT"]),
  slug: z.string().min(1, "Slug is required").regex(/^[a-z0-9-]+$/, "Lowercase letters, numbers, hyphens only"),
  title: z.string().min(1, "Title is required"),
  body: z.string().min(1, "Body is required"),
  meta: z.string().optional(),
  sortOrder: z.number().int().min(0).optional(),
  state: z.string().optional(),
  lga: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

interface ContentItemFormProps {
  item?: ContentItemDto | null;
  defaultType?: ContentItemType;
  onClose: () => void;
}

export default function ContentItemForm({ item, defaultType, onClose }: ContentItemFormProps) {
  const isEditing = !!item;
  const createMutation = useCreateContentItemMutation();
  const updateMutation = useUpdateContentItemMutation();
  const isPending = createMutation.isPending || updateMutation.isPending;
  const serverError = createMutation.error || updateMutation.error;

  const {
    register,
    handleSubmit,
    watch,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      itemType: item?.itemType ?? defaultType ?? "FAQ",
      slug: item?.slug ?? "",
      title: item?.title ?? "",
      body: item?.body ?? "",
      meta: item?.meta ?? "",
      sortOrder: item?.sortOrder ?? 0,
      state: item?.state ?? "",
      lga: item?.lga ?? "",
    },
  });

  useEffect(() => {
    if (item) {
      reset({
        itemType: item.itemType,
        slug: item.slug,
        title: item.title,
        body: item.body,
        meta: item.meta ?? "",
        sortOrder: item.sortOrder,
        state: item.state ?? "",
        lga: item.lga ?? "",
      });
    }
  }, [item, reset]);

  const watchedType = watch("itemType");
  const isAreaInsight = watchedType === "AREA_INSIGHT";

  const onSubmit = handleSubmit(async (values) => {
    const payload = {
      itemType: values.itemType,
      slug: values.slug,
      title: values.title,
      body: values.body,
      meta: values.meta || undefined,
      sortOrder: values.sortOrder,
      state: isAreaInsight ? values.state || undefined : undefined,
      lga: isAreaInsight ? values.lga || undefined : undefined,
    };

    if (isEditing && item) {
      await updateMutation.mutateAsync({ itemId: item.id, payload });
    } else {
      await createMutation.mutateAsync(payload);
    }
    onClose();
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold" style={{ color: "var(--brand-navy)" }}>
          {isEditing ? "Edit Content Item" : "New Content Item"}
        </h3>
        <button
          type="button"
          className="text-sm"
          style={{ color: "var(--brand-on-surface-variant)" }}
          onClick={onClose}
        >
          ← Back
        </button>
      </div>

      <form onSubmit={onSubmit} className="space-y-4">
        {/* Item Type */}
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: "var(--brand-on-surface-variant)" }}>
            Type
          </label>
          <select
            {...register("itemType")}
            disabled={isEditing}
            className="w-full rounded-lg px-3 py-2 text-sm border"
            style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-navy)", background: "var(--brand-surface)" }}
          >
            {CONTENT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          {errors.itemType && <p className="text-xs text-red-500 mt-1">{errors.itemType.message}</p>}
        </div>

        {/* Slug */}
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: "var(--brand-on-surface-variant)" }}>
            Slug
          </label>
          <input
            {...register("slug")}
            type="text"
            placeholder="e.g. how-it-works-step-1"
            className="w-full rounded-lg px-3 py-2 text-sm border"
            style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-navy)", background: "var(--brand-surface)" }}
          />
          {errors.slug && <p className="text-xs text-red-500 mt-1">{errors.slug.message}</p>}
        </div>

        {/* Title */}
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: "var(--brand-on-surface-variant)" }}>
            Title
          </label>
          <input
            {...register("title")}
            type="text"
            placeholder="Content title"
            className="w-full rounded-lg px-3 py-2 text-sm border"
            style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-navy)", background: "var(--brand-surface)" }}
          />
          {errors.title && <p className="text-xs text-red-500 mt-1">{errors.title.message}</p>}
        </div>

        {/* Body */}
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: "var(--brand-on-surface-variant)" }}>
            Body
          </label>
          <textarea
            {...register("body")}
            rows={5}
            placeholder="Content body (markdown supported)"
            className="w-full rounded-lg px-3 py-2 text-sm border resize-none"
            style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-navy)", background: "var(--brand-surface)" }}
          />
          {errors.body && <p className="text-xs text-red-500 mt-1">{errors.body.message}</p>}
        </div>

        {/* Area Insight fields */}
        {isAreaInsight && (
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium mb-1" style={{ color: "var(--brand-on-surface-variant)" }}>
                State
              </label>
              <input
                {...register("state")}
                type="text"
                placeholder="e.g. Lagos"
                className="w-full rounded-lg px-3 py-2 text-sm border"
                style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-navy)", background: "var(--brand-surface)" }}
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1" style={{ color: "var(--brand-on-surface-variant)" }}>
                LGA
              </label>
              <input
                {...register("lga")}
                type="text"
                placeholder="e.g. Ikeja"
                className="w-full rounded-lg px-3 py-2 text-sm border"
                style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-navy)", background: "var(--brand-surface)" }}
              />
            </div>
          </div>
        )}

        {/* Sort Order + Meta in a row */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "var(--brand-on-surface-variant)" }}>
              Sort Order
            </label>
            <input
              {...register("sortOrder", { valueAsNumber: true })}
              type="number"
              min={0}
              className="w-full rounded-lg px-3 py-2 text-sm border"
              style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-navy)", background: "var(--brand-surface)" }}
            />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "var(--brand-on-surface-variant)" }}>
              Meta (JSON, optional)
            </label>
            <input
              {...register("meta")}
              type="text"
              placeholder='{"icon": "home"}'
              className="w-full rounded-lg px-3 py-2 text-sm border"
              style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-navy)", background: "var(--brand-surface)" }}
            />
          </div>
        </div>

        {serverError && (
          <p className="text-sm text-red-600">{getErrorMessage(serverError)}</p>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm border"
            style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-on-surface-variant)" }}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isPending}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
            style={{ background: "var(--brand-viridian)" }}
          >
            {isPending ? "Saving…" : isEditing ? "Save Changes" : "Create Item"}
          </button>
        </div>
      </form>
    </div>
  );
}
