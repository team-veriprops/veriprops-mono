"use client";

import { useState } from "react";
import Link from "next/link";
import { Megaphone, Plus } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { Card } from "@3rdparty/ui/card";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import {
  useBroadcastsQuery,
  useCancelBroadcastMutation,
  useSendBroadcastMutation,
} from "./libs/useBroadcastQueries";
import { Broadcast, BroadcastStatus } from "@/types/broadcast";
import { Page } from "@/types/models";
import { ROUTES } from "@lib/routes";
import { humanizeEnumLabel } from "@lib/utils";

const STATUS_TONE: Record<BroadcastStatus, string> = {
  [BroadcastStatus.DRAFT]: "bg-muted text-muted-foreground",
  [BroadcastStatus.SCHEDULED]: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  [BroadcastStatus.SENT]: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  [BroadcastStatus.CANCELLED]: "bg-red-500/10 text-red-600 dark:text-red-400",
};

/** Broadcast management (§18.1) — the audience announcements list + row actions. */
export default function AdminBroadcasts() {
  const [page, setPage] = useState(0);
  const { data, isLoading, isError } = useBroadcastsQuery(page);
  const sendMutation = useSendBroadcastMutation();
  const cancelMutation = useCancelBroadcastMutation();

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 p-4 sm:p-6" data-testid="admin-broadcasts">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Megaphone className="size-6 text-primary" aria-hidden />
          <h1 className="text-2xl font-bold text-foreground">Broadcasts</h1>
        </div>
        <Button asChild size="sm">
          <Link href={ROUTES.ADMIN.BROADCAST_NEW}>
            <Plus className="size-4" /> New broadcast
          </Link>
        </Button>
      </div>

      <AsyncStateComponent<Page<Broadcast>> isLoading={isLoading} isError={isError} data={data}>
        {(pageData) =>
          pageData.items.length === 0 ? (
            <Card className="p-8 text-center text-sm text-muted-foreground">No broadcasts yet.</Card>
          ) : (
            <ul className="space-y-2">
              {pageData.items.map((b) => (
                <li key={b.id}>
                  <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-w-0 space-y-1">
                      <p className="truncate font-medium text-foreground">{b.subject}</p>
                      <p className="text-xs text-muted-foreground">
                        {b.audience} · {b.recipientCount} recipients
                        {b.scheduledAt ? ` · scheduled ${new Date(b.scheduledAt).toLocaleString()}` : ""}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_TONE[b.status]}`}>
                        {humanizeEnumLabel(b.status)}
                      </span>
                      {(b.status === BroadcastStatus.DRAFT || b.status === BroadcastStatus.SCHEDULED) && (
                        <>
                          <Button size="sm" variant="outline" onClick={() => sendMutation.mutate(b.id)} disabled={sendMutation.isPending}>
                            Send now
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => cancelMutation.mutate(b.id)} disabled={cancelMutation.isPending}>
                            Cancel
                          </Button>
                        </>
                      )}
                    </div>
                  </Card>
                </li>
              ))}
            </ul>
          )
        }
      </AsyncStateComponent>

      <div className="flex items-center justify-between">
        <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
          Previous
        </Button>
        <span className="text-xs text-muted-foreground">Page {page + 1}</span>
        <Button
          variant="outline"
          size="sm"
          disabled={!data || data.items.length < 10}
          onClick={() => setPage((p) => p + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
