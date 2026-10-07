"use client";

import { Button } from "@3rdparty/ui/button";
import { Card } from "@3rdparty/ui/card";
import { Broadcast, BroadcastAction, BroadcastStatus } from "@/types/broadcast";
import { formatCount, humanizeEnumLabel } from "@lib/utils";

const STATUS_TONE: Record<BroadcastStatus, string> = {
  [BroadcastStatus.DRAFT]: "bg-muted text-muted-foreground",
  [BroadcastStatus.SCHEDULED]: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  [BroadcastStatus.SENDING]: "bg-sky-500/10 text-sky-700 dark:text-sky-400",
  [BroadcastStatus.SENT]: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  [BroadcastStatus.CANCELLED]: "bg-red-500/10 text-red-600 dark:text-red-400",
};

/** How far the broadcast has reached its audience, in the words its status calls for. */
function reach(b: Broadcast): string {
  const reached = formatCount(b.recipientsEnqueued);
  const audience = formatCount(b.recipientCount);
  switch (b.status) {
    case BroadcastStatus.SENDING:
      return `${reached} of ${audience} recipients reached`;
    case BroadcastStatus.SENT:
      return `${formatCount(b.recipientsEnqueued || b.recipientCount)} recipients`;
    case BroadcastStatus.CANCELLED:
      return b.recipientsEnqueued > 0 ? `stopped after ${reached} of ${audience} recipients` : "not sent";
    default:
      return "not sent yet";
  }
}

interface BroadcastRowProps {
  broadcast: Broadcast;
  onSend: (id: string) => void;
  onCancel: (id: string) => void;
  busy: boolean;
}

/** One broadcast in the admin list (§18.1): what it reached, and the actions the backend allows. */
export default function BroadcastRow({ broadcast: b, onSend, onCancel, busy }: BroadcastRowProps) {
  const can = (action: BroadcastAction) => b.allowedActions.includes(action);
  return (
    <Card
      className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between"
      data-testid={`broadcast-${b.id}`}
    >
      <div className="min-w-0 space-y-1">
        <p className="truncate font-medium text-foreground">{b.subject}</p>
        <p className="text-xs text-muted-foreground" data-testid={`broadcast-reach-${b.id}`}>
          {humanizeEnumLabel(b.audience)} · {reach(b)}
          {b.scheduledAt && b.status === BroadcastStatus.SCHEDULED
            ? ` · scheduled ${new Date(b.scheduledAt).toLocaleString()}`
            : ""}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_TONE[b.status]}`}
          data-testid={`broadcast-status-${b.id}`}
        >
          {humanizeEnumLabel(b.status)}
        </span>
        {can(BroadcastAction.SEND) && (
          <Button size="sm" variant="outline" onClick={() => onSend(b.id)} disabled={busy}
                  data-testid={`broadcast-send-${b.id}`}>
            Send now
          </Button>
        )}
        {can(BroadcastAction.CANCEL) && (
          <Button size="sm" variant="ghost" onClick={() => onCancel(b.id)} disabled={busy}
                  data-testid={`broadcast-cancel-${b.id}`}>
            {b.status === BroadcastStatus.SENDING ? "Stop" : "Cancel"}
          </Button>
        )}
      </div>
    </Card>
  );
}
