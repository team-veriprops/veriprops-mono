"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { Download, Loader2 } from "lucide-react";
import AccountShell from "@components/account/AccountShell";

interface ConsentHistoryItem {
  documentType: string;
  consentVersion: string;
  acceptedAt: string;
  ipAddress: string | null;
  deviceFingerprint: string | null;
}

interface ConsentHistoryPage {
  items: ConsentHistoryItem[];
  total: number;
  page: number;
  pageSize: number;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const TYPE_LABELS: Record<string, string> = {
  TERMS_OF_SERVICE: "Terms of Service",
  PRIVACY_POLICY: "Privacy Policy",
  AGENT_TERMS: "Agent Terms",
  VERIFICATION_CONSENT: "Verification Consent",
};

export default function ConsentsPage() {
  const [page, setPage] = useState(0);

  const { data, isLoading, error } = useQuery<{ data: ConsentHistoryPage }>({
    queryKey: ["account", "consents", page],
    queryFn: () => httpClient.get(`/account/consents/history?page=${page}&page_size=20`),
    staleTime: 60_000,
  });

  const history = (data as any)?.data ?? null;

  const handleDownload = () => {
    window.open("/api/account/consents/history/download", "_blank");
  };

  return (
    <AccountShell
      title="Consent history"
      subtitle="All agreements you have accepted on Veriprops."
    >
      <div className="flex justify-end mb-6">
        <button
          onClick={handleDownload}
          className="flex items-center gap-1.5 text-sm border rounded-lg px-3 py-1.5 transition-colors hover:bg-[var(--brand-surface-low)]"
          style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-on-surface-variant)", cursor: "pointer" }}
        >
          <Download className="h-4 w-4" />
          Download CSV
        </button>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin" style={{ color: "var(--brand-viridian)" }} />
        </div>
      )}

      {error && (
        <p className="text-sm" style={{ color: "var(--danger)" }}>Unable to load consent history.</p>
      )}

      {!isLoading && history && history.items.length === 0 && (
        <div
          className="rounded-xl p-10 text-center"
          style={{ backgroundColor: "var(--brand-surface-card)", boxShadow: "var(--shadow-card)" }}
        >
          <p className="text-base font-semibold" style={{ color: "var(--brand-navy)" }}>No consent records found</p>
          <p className="text-sm mt-1.5" style={{ color: "var(--brand-on-surface-variant)" }}>
            Agreements you accept will appear here.
          </p>
        </div>
      )}

      {history && history.items.length > 0 && (
        <>
          <div
            className="rounded-xl overflow-hidden"
            style={{ backgroundColor: "var(--brand-surface-card)", boxShadow: "var(--shadow-card)" }}
          >
            {history.items.map((item: ConsentHistoryItem, i: number) => (
              <div
                key={i}
                className="px-5 py-4 flex items-start justify-between gap-4"
                style={{ borderBottom: i < history.items.length - 1 ? "1px solid rgba(196,198,207,0.12)" : "none" }}
              >
                <div>
                  <p className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>
                    {TYPE_LABELS[item.documentType] ?? item.documentType}
                  </p>
                  <p className="text-xs mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
                    Version {item.consentVersion}
                    {item.ipAddress ? ` · ${item.ipAddress}` : ""}
                  </p>
                </div>
                <p className="text-xs shrink-0 mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
                  {formatDate(item.acceptedAt)}
                </p>
              </div>
            ))}
          </div>

          {history.total > history.pageSize && (
            <div className="flex items-center justify-between mt-4 text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="disabled:opacity-40"
                style={{ cursor: page === 0 ? "default" : "pointer" }}
              >
                Previous
              </button>
              <span>Page {page + 1} of {Math.ceil(history.total / history.pageSize)}</span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={(page + 1) * history.pageSize >= history.total}
                className="disabled:opacity-40"
                style={{ cursor: (page + 1) * history.pageSize >= history.total ? "default" : "pointer" }}
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </AccountShell>
  );
}
