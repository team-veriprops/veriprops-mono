"use client";

import { useState } from "react";
import Link from "next/link";
import { Megaphone, Plus } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { Card } from "@3rdparty/ui/card";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import BroadcastRow from "./BroadcastRow";
import {
  useBroadcastsQuery,
  useCancelBroadcastMutation,
  useSendBroadcastMutation,
} from "./libs/useBroadcastQueries";
import { Broadcast } from "@/types/broadcast";
import { Page } from "@/types/models";
import { ROUTES } from "@lib/routes";

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
                  <BroadcastRow
                    broadcast={b}
                    onSend={(id) => sendMutation.mutate(id)}
                    onCancel={(id) => cancelMutation.mutate(id)}
                    busy={sendMutation.isPending || cancelMutation.isPending}
                  />
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
          disabled={!data || page + 1 >= data.meta.totalPages}
          onClick={() => setPage((p) => p + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
