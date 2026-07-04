"use client";

import Link from "next/link";
import { ChevronRight, Plus } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { Card } from "@3rdparty/ui/card";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { ROUTES } from "@lib/routes";
import { useMyVerificationsQuery } from "@components/portal/libs/useVerificationQueries";
import { Page } from "@/types/models";
import { VerificationListItem } from "@/types/tracking";
import { VerificationStatusBadge } from "./VerificationStatusBadge";

/** The customer's "My Verifications" list (§9) — mobile-first cards → tracking. */
export default function MyVerificationsList() {
  const { data, isLoading, isError } = useMyVerificationsQuery();

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 sm:p-6" data-testid="verify-list">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">My Verifications</h1>
        <Button asChild size="sm">
          <Link href={ROUTES.PORTAL.VERIFICATIONS_NEW}>
            <Plus className="size-4" /> New
          </Link>
        </Button>
      </div>

      <AsyncStateComponent<Page<VerificationListItem>>
        isLoading={isLoading}
        isError={isError}
        data={data}
        emptyText="You have no verifications yet."
      >
        {(page) =>
          page.items.length === 0 ? (
            <EmptyState />
          ) : (
            <ul className="space-y-2">
              {page.items.map((v) => (
                <li key={v.id}>
                  <Link href={ROUTES.PORTAL.VERIFICATION_TRACKING(v.id)}>
                    <Card className="flex items-center justify-between gap-3 p-4 transition hover:border-primary">
                      <div className="min-w-0 space-y-1">
                        <p className="truncate font-medium">{v.address ?? v.vid}</p>
                        <p className="text-xs text-muted-foreground">
                          {v.vid}{v.tier ? ` · ${v.tier}` : ""}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <VerificationStatusBadge status={v.status} label={v.statusLabel} />
                        <ChevronRight className="size-4 text-muted-foreground" />
                      </div>
                    </Card>
                  </Link>
                </li>
              ))}
            </ul>
          )
        }
      </AsyncStateComponent>
    </div>
  );
}

function EmptyState() {
  return (
    <Card className="flex flex-col items-center gap-3 p-8 text-center">
      <p className="text-sm text-muted-foreground">
        Start your first property verification to see it tracked live here.
      </p>
      <Button asChild>
        <Link href={ROUTES.PORTAL.VERIFICATIONS_NEW}>Start a verification</Link>
      </Button>
    </Card>
  );
}
