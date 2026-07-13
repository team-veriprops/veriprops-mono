"use client";

import { useState } from "react";
import { DEFAULT_HISTORY_PAGE_SIZE } from "@lib/config/app";
import { ShieldAlert, ShieldCheck, Loader2 } from "lucide-react";

import { useSecurityEventsQuery } from "@components/website/auth/libs/useAuthQueries";
import { SecurityEventType } from "@components/website/auth/models";
import { Button } from "@3rdparty/ui/button";
import { humanizeEnumLabel, cn } from "@lib/utils";

const PAGE_SIZE = DEFAULT_HISTORY_PAGE_SIZE;

// Risk-signalling events get a warning style in the log.
const RISK_EVENTS = new Set<string>([
  SecurityEventType.LOGIN_FAILURE_WARNING,
  SecurityEventType.LOGIN_FAILURE,
  SecurityEventType.ACCOUNT_LOCKED,
  SecurityEventType.OTP_FAILURE,
]);

export default function SecurityActivityPage() {
  const [page, setPage] = useState(0);
  const { data, isLoading, isError } = useSecurityEventsQuery(page, PAGE_SIZE);

  const events = data?.items ?? [];
  const meta = data?.meta;
  const totalPages = meta?.totalPages ?? 1;

  return (
    <div className="max-w-4xl mx-auto px-4 md:px-8 py-8" data-testid="security-events">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-brand-navy">
          Security Activity
        </h1>
        <p className="text-sm mt-1 text-brand-on-surface-variant">
          Recent sign-ins, password changes, and security events on your account.
        </p>
      </header>

      {isLoading ? (
        <div className="flex items-center gap-2 py-12 justify-center text-brand-on-surface-variant">
          <Loader2 className="w-5 h-5 animate-spin" /> Loading activity…
        </div>
      ) : isError ? (
        <p className="py-12 text-center text-sm text-danger">
          Could not load your security activity. Please try again.
        </p>
      ) : events.length === 0 ? (
        <p className="py-12 text-center text-sm text-brand-on-surface-variant">
          No security activity yet.
        </p>
      ) : (
        <ul className="space-y-2" data-testid="security-events-list">
          {events.map((e) => {
            const risk = RISK_EVENTS.has(e.type);
            return (
              <li
                key={e.id}
                data-testid="security-event-row"
                data-event-type={e.type}
                className="flex items-start gap-3 rounded-xl p-4 bg-brand-surface-card shadow-card"
              >
                <span
                  className={cn(
                    "w-9 h-9 rounded-lg flex items-center justify-center shrink-0",
                    risk ? "bg-brand-gold-xlight text-brand-gold" : "bg-brand-viridian-xlight text-brand-viridian"
                  )}
                >
                  {risk ? <ShieldAlert className="w-5 h-5" /> : <ShieldCheck className="w-5 h-5" />}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-brand-navy">
                    {humanizeEnumLabel(e.type)}
                  </p>
                  <p className="text-sm text-brand-on-surface-variant">
                    {e.description}
                  </p>
                  <p className="text-xs mt-1 text-brand-on-surface-variant/55">
                    {new Date(e.occurredAt).toLocaleString()}
                    {e.ipAddress ? ` · ${e.ipAddress}` : ""}
                    {e.device ? ` · ${e.device}` : ""}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {meta && totalPages > 1 && (
        <div className="flex items-center justify-between mt-6">
          <Button
            variant="outline"
            disabled={page <= 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            data-testid="security-events-prev"
          >
            Previous
          </Button>
          <span className="text-xs text-brand-on-surface-variant">
            Page {page + 1} of {totalPages}
          </span>
          <Button
            variant="outline"
            disabled={page + 1 >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            data-testid="security-events-next"
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}

