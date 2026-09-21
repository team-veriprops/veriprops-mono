"use client";

import { useState } from "react";
import { DEFAULT_HISTORY_PAGE_SIZE } from "@lib/config/app";
import ListPager from "@components/ui/ListPager";
import { ActivityTimeline } from "@components/shared/activity/ActivityTimeline";
import { useVerificationActivityQuery } from "../libs/useVerificationQueries";

const PAGE_SIZE = DEFAULT_HISTORY_PAGE_SIZE;

/** Customer-facing verification activity log (§19.2) — backend-owned, PII-safe. */
export default function VerificationActivity({ verificationId }: { verificationId: string }) {
  const [page, setPage] = useState(0);
  const { data, isLoading, isError } = useVerificationActivityQuery(verificationId, page);
  const events = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="max-w-3xl mx-auto px-4 md:px-8 py-8" data-testid="verification-activity">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-brand-navy">Activity</h1>
        <p className="text-sm mt-1 text-brand-on-surface-variant">
          Every step your verification has moved through, in order.
        </p>
      </header>

      <ActivityTimeline
        events={events}
        isLoading={isLoading}
        isError={isError}
        emptyLabel="No activity recorded yet."
      />

      <ListPager page={page} totalPages={totalPages} onPageChange={setPage} className="mt-6" />
    </div>
  );
}
