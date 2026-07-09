"use client";

import { useState } from "react";
import { Loader2, Download, FileText } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { humanizeEnumLabel } from "@lib/utils";
import { UserConsentHistoryItem } from "@/types/consentHistory";
import { useConsentHistoryQuery, consentHistoryService } from "./libs/useConsentHistoryQueries";

const PAGE_SIZE = 20;

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
          <h1 className="text-2xl font-bold" style={{ color: "var(--brand-navy)" }}>Consents</h1>
          <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
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
        <div className="flex items-center gap-2 py-12 justify-center" style={{ color: "var(--brand-on-surface-variant)" }}>
          <Loader2 className="w-5 h-5 animate-spin" /> Loading consents…
        </div>
      ) : isError ? (
        <p className="py-12 text-center text-sm" style={{ color: "var(--brand-destructive, #ba1a1a)" }}>
          Could not load your consent history. Please try again.
        </p>
      ) : items.length === 0 ? (
        <p className="py-12 text-center text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
          You have not accepted any versioned agreements yet.
        </p>
      ) : (
        <ul className="space-y-2">
          {items.map((c, i) => (
            <li
              key={`${c.documentType}-${c.consentVersion}-${i}`}
              className="flex items-start gap-3 rounded-xl p-4"
              style={{ backgroundColor: "var(--brand-surface-card)", boxShadow: "0 1px 3px rgba(0,13,34,0.06)" }}
            >
              <span
                className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
                style={{ backgroundColor: "var(--brand-viridian-xlight)", color: "var(--brand-viridian)" }}
              >
                <FileText className="w-5 h-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>
                  {humanizeEnumLabel(c.documentType)} <span className="font-normal text-xs">v{c.consentVersion}</span>
                </p>
                <p className="text-xs mt-1" style={{ color: "rgba(68,71,78,0.55)" }}>
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
