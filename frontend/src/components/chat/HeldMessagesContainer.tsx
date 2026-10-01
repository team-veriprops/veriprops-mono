"use client";

import { Check, X } from "lucide-react";
import { toast } from "sonner";
import { useHeldQueueQuery, useReviewMessageMutation } from "./libs/useChatQueries";
import { getErrorMessage } from "@lib/errors";
import { humanizeEnumLabel } from "@lib/utils";

/**
 * Admin hold-review queue (§11.2). Flagged messages wait here for approve (deliver) or
 * reject (block). Each item shows the raw body + why it was held, so decisions are informed
 * and the false-positive rate can be tuned.
 *
 * Renders as a tab panel inside `AdminMessagesTabs`, so the page title and container come
 * from the shell rather than from here.
 */
export default function HeldMessagesContainer() {
  const { data, isLoading } = useHeldQueueQuery(0);
  const review = useReviewMessageMutation();
  const items = data?.items ?? [];
  const decide = (messageId: string, approve: boolean) =>
    review.mutate(
      { messageId, approve },
      { onError: (err) => toast.error(getErrorMessage(err, "Could not review the message.")) },
    );

  return (
    <div>
      <p className="text-sm text-brand-on-surface-variant mb-5">
        Messages flagged for off-platform contact or payment details are held here. Approve to
        deliver, or reject to block.
      </p>

      {isLoading && <p className="text-sm text-brand-on-surface-variant">Loading…</p>}
      {!isLoading && items.length === 0 && (
        <div className="text-center py-12 rounded-xl border border-black/5 bg-white">
          <Check className="w-8 h-8 mx-auto text-gray-300 mb-2" />
          <p className="text-sm text-brand-on-surface-variant">Nothing to review — the queue is clear.</p>
        </div>
      )}

      <ul className="space-y-3">
        {items.map((m) => (
          <li key={m.id} className="rounded-xl border border-black/5 bg-white p-4" data-testid="held-message">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <span className="text-xs font-medium text-brand-on-surface-variant">{humanizeEnumLabel(m.senderKind)}</span>
              {m.flaggedCategories.map((c) => (
                <span
                  key={c}
                  className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-danger/8 text-danger"
                >
                  {humanizeEnumLabel(c)}
                </span>
              ))}
            </div>
            <p className="text-sm mb-3 whitespace-pre-wrap text-brand-navy">
              {m.body}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => decide(m.id, true)}
                disabled={review.isPending}
                data-testid="held-message-approve"
                className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg text-white bg-brand-viridian disabled:opacity-50"
              >
                <Check className="w-3.5 h-3.5" /> Approve
              </button>
              <button
                onClick={() => decide(m.id, false)}
                disabled={review.isPending}
                data-testid="held-message-reject"
                className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg border border-black/10 text-brand-on-surface-variant disabled:opacity-50"
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
