"use client";

import { useState } from "react";
import { DEFAULT_HISTORY_PAGE_SIZE } from "@lib/config/app";
import { Button } from "@3rdparty/ui/button";
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
        <h1 className="text-2xl font-bold" style={{ color: "var(--brand-navy)" }}>Activity</h1>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          Every step your verification has moved through, in order.
        </p>
      </header>

      <ActivityTimeline
        events={events}
        isLoading={isLoading}
        isError={isError}
        emptyLabel="No activity recorded yet."
      />

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-6">
          <Button variant="outline" disabled={page <= 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
            Previous
          </Button>
          <span className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
            Page {page + 1} of {totalPages}
          </span>
          <Button variant="outline" disabled={page + 1 >= totalPages} onClick={() => setPage((p) => p + 1)}>
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
