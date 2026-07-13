"use client";

import { ShieldAlert, Check, X } from "lucide-react";
import { useHeldQueueQuery, useReviewMessageMutation } from "./libs/useChatQueries";

/**
 * Admin hold-review queue (§11.2). Flagged messages wait here for approve (deliver) or
 * reject (block). Each item shows the raw body + why it was held, so decisions are informed
 * and the false-positive rate can be tuned.
 */
export default function HeldMessagesContainer() {
  const { data, isLoading } = useHeldQueueQuery(0);
  const review = useReviewMessageMutation();
  const items = data?.items ?? [];

  return (
    <div className="max-w-3xl mx-auto p-6">
      <div className="flex items-center gap-3 mb-1">
        <ShieldAlert className="w-5 h-5 text-brand-viridian" />
        <h1 className="text-xl font-semibold text-brand-navy">
          Message review
        </h1>
      </div>
      <p className="text-sm text-gray-500 mb-5">
        Messages flagged for off-platform contact or payment details are held here. Approve to
        deliver, or reject to block.
      </p>

      {isLoading && <p className="text-sm text-gray-400">Loading…</p>}
      {!isLoading && items.length === 0 && (
        <div className="text-center py-12 rounded-xl border border-black/5 bg-white">
          <Check className="w-8 h-8 mx-auto text-gray-300 mb-2" />
          <p className="text-sm text-gray-500">Nothing to review — the queue is clear.</p>
        </div>
      )}

      <ul className="space-y-3">
        {items.map((m) => (
          <li key={m.id} className="rounded-xl border border-black/5 bg-white p-4">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <span className="text-xs font-medium text-gray-500">{m.senderKind}</span>
              {m.flaggedCategories.map((c) => (
                <span
                  key={c}
                  className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-danger/8 text-danger"
                >
                  {c}
                </span>
              ))}
            </div>
            <p className="text-sm mb-3 whitespace-pre-wrap text-brand-navy">
              {m.body}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => review.mutate({ messageId: m.id, approve: true })}
                disabled={review.isPending}
                className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg text-white bg-brand-viridian disabled:opacity-50"
              >
                <Check className="w-3.5 h-3.5" /> Approve
              </button>
              <button
                onClick={() => review.mutate({ messageId: m.id, approve: false })}
                disabled={review.isPending}
                className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg border border-black/10 text-gray-600 disabled:opacity-50"
              >
                <X className="w-3.5 h-3.5" /> Reject
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
