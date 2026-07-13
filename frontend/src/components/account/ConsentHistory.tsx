"use client";

import { useState } from "react";
import { DEFAULT_HISTORY_PAGE_SIZE } from "@lib/config/app";
import { Loader2, Download, FileText } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { cn, humanizeEnumLabel } from "@lib/utils";
import { UserConsentHistoryItem } from "@/types/consentHistory";
import { useConsentHistoryQuery, consentHistoryService } from "./libs/useConsentHistoryQueries";

const PAGE_SIZE = DEFAULT_HISTORY_PAGE_SIZE;

/** Account → Consents (§19.1 / R19.4). Versioned consent history + CSV download. */
export default function ConsentHistory() {
  const [page, setPage] = useState(0);
  const { data, isLoading, isError } = useConsentHistoryQuery(page);
  const items: UserConsentHistoryItem[] = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="max-w-3xl mx-auto px-4 md:px-8 py-8" data-testid="consent-history">
      <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className={cn("text-2xl font-bold text-brand-navy")}>Consents</h1>
          <p className={cn("text-sm mt-1 text-brand-on-surface-variant")}>
            The versioned agreements you have accepted, with the date and version.
          </p>
        </div>
        <a href={consentHistoryService.downloadUrl()} target="_blank" rel="noopener noreferrer" data-testid="consent-download">
          <Button variant="outline">
            <Download className="w-4 h-4 mr-2" /> Download CSV
          </Button>
        </a>
      </header>

      {isLoading ? (
        <div className={cn("flex items-center gap-2 py-12 justify-center text-brand-on-surface-variant")}>
          <Loader2 className="w-5 h-5 animate-spin" /> Loading consents…
        </div>
      ) : isError ? (
        <p className={cn("py-12 text-center text-sm text-destructive")}>
          Could not load your consent history. Please try again.
        </p>
      ) : items.length === 0 ? (
        <p className={cn("py-12 text-center text-sm text-brand-on-surface-variant")}>
          You have not accepted any versioned agreements yet.
        </p>
      ) : (
        <ul className="space-y-2">
          {items.map((c, i) => (
            <li
              key={`${c.documentType}-${c.consentVersion}-${i}`}
              className={cn("flex items-start gap-3 rounded-xl p-4 bg-brand-surface-card shadow-card")}
            >
              <span
                className={cn("w-9 h-9 rounded-lg flex items-center justify-center shrink-0 bg-brand-viridian-xlight text-brand-viridian")}
              >
                <FileText className="w-5 h-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className={cn("text-sm font-semibold text-brand-navy")}>
                  {humanizeEnumLabel(c.documentType)} <span className="font-normal text-xs">v{c.consentVersion}</span>
                </p>
                <p className={cn("text-xs mt-1 text-brand-on-surface-variant/55")}>
                  Accepted {new Date(c.acceptedAt).toLocaleString()}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-6">
          <Button variant="outline" disabled={page <= 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
            Previous
          </Button>
          <span className={cn("text-xs text-brand-on-surface-variant")}>
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
